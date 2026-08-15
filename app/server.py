"""Localhost-only HTTP server for the SHION web chat MVP."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.shion_runtime import ShionRuntime  # noqa: E402
from app.core.gpu_resource_gate import (GpuResourceGate, ResourceGateCancelled,
                                        ResourceGateFull, ResourceGateTimeout)  # noqa: E402
from app.characters.registry import CharacterRegistry  # noqa: E402
from app.memory.service import SensitiveMemoryError  # noqa: E402
from app.models.registry import ModelRegistry  # noqa: E402
from app.runtime.model_runtime import LocalModelRuntime  # noqa: E402
from app.storage.conversation_db import ConversationRepository  # noqa: E402
from app.storage.paths import StoragePaths  # noqa: E402
from app.voice.service import VoiceServiceClient, VoiceUnavailable  # noqa: E402


STATIC = Path(__file__).resolve().parent / "static"
REGISTRY_PATH = Path(__file__).resolve().parent / "model_registry.json"
CHARACTER_ROOT = STATIC / "assets" / "characters"
MAX_BODY_BYTES = 128 * 1024
LOG = logging.getLogger("shion_web")
SAFE_DIAGNOSTIC_HEADERS = (
    "Host", "Origin", "Referer", "Forwarded", "X-Forwarded-For",
    "X-Forwarded-Host", "X-Forwarded-Proto", "Tailscale-User-Login",
    "Tailscale-User-Name", "Tailscale-User-Profile-Pic", "Tailscale-App-Capabilities",
)


def _hostname(value: str) -> str:
    try:
        parsed = urlparse(value if "://" in value else f"//{value}")
        return (parsed.hostname or "").rstrip(".").lower()
    except ValueError:
        return ""


def discover_tailscale_hosts() -> set[str]:
    """Return this node's exact Serve hostnames; fail closed when unavailable."""
    hosts: set[str] = set()
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self_node = json.loads(result.stdout).get("Self", {})
        for value in (self_node.get("HostName"), self_node.get("DNSName")):
            host = _hostname(str(value or ""))
            if host:
                hosts.add(host)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        LOG.warning("Tailscale hostname discovery unavailable; Tailscale Serve access disabled")
    extra = os.environ.get("SHION_TAILSCALE_HOSTS", "")
    hosts.update(host for host in (_hostname(item.strip()) for item in extra.split(",")) if host)
    return hosts


class RuntimeController(ShionRuntime):
    """Compatibility facade for the original server import path."""

    def __init__(self, registry: dict | None = None, conversations: ConversationRepository | None = None) -> None:
        model_registry = (
            ModelRegistry(registry) if registry is not None else ModelRegistry.from_file(REGISTRY_PATH)
        )
        super().__init__(
            model_registry,
            model_factory=lambda common, alias, spec, adapter: LocalModelRuntime(common, alias, spec, adapter),
            conversations=conversations,
        )


class ShionServer(ThreadingHTTPServer):
    # Refuse a duplicate Windows bind before a second process allocates a model.
    allow_reuse_address = False
    controller: RuntimeController
    tailscale_hosts: frozenset[str]
    voice: VoiceServiceClient | None
    gpu_gate: GpuResourceGate
    characters: CharacterRegistry
    storage_root: Path


class Handler(BaseHTTPRequestHandler):
    server: ShionServer

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _safe_request_diagnostics(self) -> dict[str, object]:
        return {
            "client_address": self.client_address[0],
            "headers": {name: self.headers.get(name, "")[:512] for name in SAFE_DIAGNOSTIC_HEADERS if self.headers.get(name)},
        }

    def _origin_matches(self, request_authority: str) -> bool:
        for name in ("Origin", "Referer"):
            value = self.headers.get(name)
            if value and urlparse(value).netloc.lower() != request_authority:
                return False
        return True

    def _access_kind(self) -> str | None:
        if self.client_address[0] != "127.0.0.1":
            return None
        request_authority = self.headers.get("Host", "").strip().lower()
        host = _hostname(request_authority)
        if host in {"127.0.0.1", "localhost"}:
            return "localhost" if self._origin_matches(request_authority) else None
        tailscale_identity = bool(
            self.headers.get("Tailscale-User-Login") or self.headers.get("Tailscale-App-Capabilities")
        )
        if host in self.server.tailscale_hosts and tailscale_identity and self._origin_matches(request_authority):
            return "tailscale-serve"
        return None

    def _allowed_host(self) -> bool:
        access_kind = self._access_kind()
        allowed = access_kind is not None
        if access_kind == "tailscale-serve":
            LOG.info("Accepted Tailscale Serve request boundary=%s", json.dumps(self._safe_request_diagnostics(), ensure_ascii=False))
        if not allowed:
            LOG.warning("Rejected request boundary=%s", json.dumps(self._safe_request_diagnostics(), ensure_ascii=False))
        return allowed

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("application/json required")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("invalid request size")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def _static(self, name: str, content_type: str) -> None:
        path = (STATIC / name).resolve()
        if STATIC.resolve() not in path.parents or not path.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._allowed_host():
            self._json(HTTPStatus.FORBIDDEN, {"error": "localhost access only"})
            return
        path = urlparse(self.path).path
        if path == "/api/status":
            status = self.server.controller.status()
            status["voice"] = self.server.voice.status() if self.server.voice else {"state": "UNAVAILABLE", "error": "Persistent history unavailable"}
            self._json(HTTPStatus.OK, status)
        elif path == "/api/voice/meta":
            self._json(HTTPStatus.OK, self.server.voice.metadata(True) if self.server.voice else {"state": "UNAVAILABLE", "approved_presets": [], "developer_models": {}})
        elif path == "/api/voice/artifacts":
            if not self.server.voice: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Voice unavailable"}); return
            character_id = parse_qs(urlparse(self.path).query).get("character_id", ["shion"])[0]
            if not character_id.isascii(): self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid character"}); return
            self._json(HTTPStatus.OK, {"artifacts": self.server.voice.list_artifacts(character_id)})
        elif path == "/api/voice/pronunciations":
            repository = self.server.controller.conversations
            if not repository: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "persistent history unavailable"}); return
            character_id = parse_qs(urlparse(self.path).query).get("character_id", ["shion"])[0]
            self._json(HTTPStatus.OK, {"rules": repository.list_pronunciation_rules(character_id)})
        elif path.startswith("/api/voice/artifacts/"):
            if not self.server.voice: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Voice unavailable"}); return
            artifact_id = path.removeprefix("/api/voice/artifacts/")
            if not artifact_id.isascii() or len(artifact_id) != 36: self._json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"}); return
            try: target, _ = self.server.voice.artifact(artifact_id)
            except (KeyError, FileNotFoundError): self._json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"}); return
            size = target.stat().st_size; start, end = 0, size - 1; response_status = HTTPStatus.OK
            requested = self.headers.get("Range")
            if requested and requested.startswith("bytes="):
                try:
                    left, right = requested[6:].split("-", 1); start = int(left or 0); end = min(int(right) if right else end, end)
                    if start > end: raise ValueError
                    response_status = HTTPStatus.PARTIAL_CONTENT
                except ValueError: self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE); return
            with target.open("rb") as handle: handle.seek(start); body = handle.read(end - start + 1)
            self.send_response(response_status); self.send_header("Content-Type", "audio/wav"); self.send_header("Accept-Ranges", "bytes")
            if response_status == HTTPStatus.PARTIAL_CONTENT: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "private, no-store"); self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(body)
        elif path == "/api/sessions":
            repository = self.server.controller.conversations
            if not repository: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "persistent history unavailable"}); return
            query = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            self._json(HTTPStatus.OK, {"sessions": repository.list_sessions(query=query)})
        elif path == "/api/characters":
            self._json(HTTPStatus.OK, {"characters": self.server.characters.list()})
        elif path.startswith("/api/characters/"):
            try: self._json(HTTPStatus.OK, self.server.characters.get(path.removeprefix("/api/characters/")))
            except KeyError: self._json(HTTPStatus.NOT_FOUND, {"error": "character not found"})
        elif path == "/api/dashboard":
            repository = self.server.controller.conversations
            sessions = repository.list_sessions(limit=6) if repository else []
            self._json(HTTPStatus.OK, {"character": self.server.characters.get("shion"), "recent_conversations": sessions,
                "runtime": self.server.controller.status(), "voice": self.server.voice.status() if self.server.voice else {"state": "UNAVAILABLE"}})
        elif path == "/api/system":
            self._json(HTTPStatus.OK, self.server.system_snapshot())
        elif path in {"/api/memory", "/api/memory/candidates"}:
            memory = self.server.controller.orchestrator.long_term_memory
            if not memory.available: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Memory unavailable"}); return
            query = parse_qs(urlparse(self.path).query)
            requested = "candidate" if path.endswith("/candidates") else query.get("status", [None])[0]
            self._json(HTTPStatus.OK, {"memories": memory.list(requested, query.get("character_id", [None])[0]),
                "automatic_promotion": False, "last_error": memory.last_error})
        elif path.startswith("/api/memory/"):
            memory = self.server.controller.orchestrator.long_term_memory
            if not memory.available: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Memory unavailable"}); return
            try: self._json(HTTPStatus.OK, memory.get(path.removeprefix("/api/memory/")))
            except KeyError: self._json(HTTPStatus.NOT_FOUND, {"error": "Memory not found"})
        elif path.startswith("/api/sessions/"):
            repository = self.server.controller.conversations
            if not repository: self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "persistent history unavailable"}); return
            session_id = path.removeprefix("/api/sessions/")
            if not session_id.isascii() or not 8 <= len(session_id) <= 80: self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid session ID"}); return
            self._json(HTTPStatus.OK, repository.load_session(session_id))
        elif path in {"/", "/index.html"}:
            self._static("index.html", "text/html; charset=utf-8")
        elif path == "/app.js":
            self._static("app.js", "text/javascript; charset=utf-8")
        elif path == "/styles.css":
            self._static("styles.css", "text/css; charset=utf-8")
        elif path == "/assets/shion/avatar.svg":
            self._static("assets/shion/avatar.svg", "image/svg+xml")
        elif path.startswith("/assets/characters/"):
            relative = path.removeprefix("/")
            suffix = Path(relative).suffix.lower()
            content_types = {".png": "image/png", ".json": "application/json; charset=utf-8"}
            if suffix not in content_types:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            self._static(relative, content_types[suffix])
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._allowed_host():
            self._json(HTTPStatus.FORBIDDEN, {"error": "localhost access only"})
            return
        try:
            payload = self._read_json()
            session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not 8 <= len(session_id) <= 80 or not session_id.isascii():
                raise ValueError("invalid session_id")
            path = urlparse(self.path).path
            if path == "/api/stop":
                stopped = self.server.controller.cancel(session_id)
                cancelled = self.server.gpu_gate.cancel(session_id=session_id)
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "stop_requested": stopped, "voice_cancelled": cancelled})
                return
            if path == "/api/voice/queue/cancel":
                message_id, version, request_id = payload.get("message_id"), payload.get("response_version"), payload.get("request_id")
                if version is not None and (not isinstance(version, int) or version < 1): raise ValueError("invalid response version")
                cancelled = self.server.gpu_gate.cancel(session_id=session_id, message_id=message_id,
                    response_version=version, request_id=request_id)
                self._json(HTTPStatus.OK, {"ok": True, "cancelled": cancelled}); return
            if path == "/api/reset":
                self.server.controller.reset(session_id)
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/sessions":
                mode = payload.get("mode", "minimal")
                if mode not in {"minimal", "neutral", "canonical"}: raise ValueError("invalid mode")
                runtime_status = self.server.controller.runtime.status() if self.server.controller.runtime else {}
                result = self.server.controller.create_persistent_session(session_id, mode, runtime_status.get("repo_id"), runtime_status.get("revision"))
                self._json(HTTPStatus.CREATED, result)
                return
            if path == "/api/sessions/rename":
                repository = self.server.controller.conversations
                if not repository: raise RuntimeError("persistent history unavailable")
                title = payload.get("title")
                if not isinstance(title, str): raise ValueError("title required")
                from datetime import datetime, timezone
                repository.rename_session(session_id, title, datetime.now(timezone.utc).isoformat(timespec="seconds"))
                self._json(HTTPStatus.OK, {"ok": True, "title": title.strip()})
                return
            if path == "/api/sessions/archive":
                repository = self.server.controller.conversations
                if not repository: raise RuntimeError("persistent history unavailable")
                from datetime import datetime, timezone
                repository.archive_session(session_id, True, datetime.now(timezone.utc).isoformat(timespec="seconds"))
                self._json(HTTPStatus.OK, {"ok": True, "archived": True})
                return
            if path == "/api/messages/favorite":
                repository = self.server.controller.conversations
                message_id, favorite = payload.get("message_id"), payload.get("favorite")
                if not repository or not isinstance(message_id, str) or not isinstance(favorite, bool): raise ValueError("invalid favorite")
                from datetime import datetime, timezone
                repository.set_favorite(message_id, favorite, datetime.now(timezone.utc).isoformat(timespec="seconds"))
                self._json(HTTPStatus.OK, {"ok": True, "favorite": favorite})
                return
            if path == "/api/messages/feedback":
                repository = self.server.controller.conversations
                message_id, rating = payload.get("message_id"), payload.get("rating")
                if not repository or not isinstance(message_id, str) or rating not in {None, "good", "bad"}: raise ValueError("invalid feedback")
                from datetime import datetime, timezone
                repository.set_feedback(message_id, rating, datetime.now(timezone.utc).isoformat(timespec="seconds"))
                self._json(HTTPStatus.OK, {"ok": True, "rating": rating})
                return
            if path == "/api/memory":
                memory = self.server.controller.orchestrator.long_term_memory
                if not memory.available: raise RuntimeError("Memory unavailable")
                allowed = {"content", "type", "scope", "character_id", "expires_at", "importance", "pinned", "metadata", "supersedes"}
                owner_payload = {key: value for key, value in payload.items() if key in allowed}
                self._json(HTTPStatus.CREATED, memory.create(owner_payload, source_author="owner")); return
            if path.startswith("/api/memory/"):
                memory = self.server.controller.orchestrator.long_term_memory
                if not memory.available: raise RuntimeError("Memory unavailable")
                suffix = path.removeprefix("/api/memory/")
                if "/" not in suffix: self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
                memory_id, action = suffix.split("/", 1)
                if action not in {"approve", "archive", "restore", "reject"}: self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
                self._json(HTTPStatus.OK, memory.transition(memory_id, action)); return
            if path == "/api/voice/generate":
                if not self.server.voice: raise VoiceUnavailable("Voice unavailable")
                message_id, version = payload.get("message_id"), payload.get("response_version", 1)
                if not isinstance(message_id, str) or not message_id.isascii() or not isinstance(version, int) or version < 1: raise ValueError("invalid Voice source")
                preset = payload.get("preset_id"); developer_model = payload.get("developer_model"); developer_style = payload.get("developer_style")
                if preset is not None and not isinstance(preset, str): raise ValueError("invalid preset")
                if developer_model is not None and (not isinstance(developer_model, str) or not developer_model.isascii()): raise ValueError("invalid developer model")
                if developer_style is not None and (not isinstance(developer_style, str) or len(developer_style) > 64): raise ValueError("invalid developer style")
                try:
                    result = self.server.voice.generate(message_id, version, preset, developer_model, developer_style,
                        bool(payload.get("retry")), session_id)
                except ValueError as error:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)}); return
                self._json(HTTPStatus.CREATED, result); return
            if path == "/api/voice/lab/generate":
                if not self.server.voice: raise VoiceUnavailable("Voice unavailable")
                text = payload.get("tts_text")
                if not isinstance(text, str): raise ValueError("tts_text required")
                parameters = payload.get("parameters", {})
                if not isinstance(parameters, dict): raise ValueError("invalid parameters")
                character_id = payload.get("character_id", "shion")
                if not isinstance(character_id, str) or not character_id.isascii(): raise ValueError("invalid character")
                self._json(HTTPStatus.CREATED, self.server.voice.generate_lab(text, parameters, session_id, character_id)); return
            if path == "/api/voice/pronunciations":
                repository = self.server.controller.conversations
                if not repository: raise RuntimeError("persistent history unavailable")
                allowed = {key: payload[key] for key in ("original_text", "replacement", "enabled", "character_id", "priority") if key in payload}
                self._json(HTTPStatus.CREATED, repository.create_pronunciation_rule(allowed)); return
            if path == "/api/voice/pronunciation/test":
                repository = self.server.controller.conversations
                text, character_id = payload.get("text"), payload.get("character_id", "shion")
                if not repository or not isinstance(text, str) or not isinstance(character_id, str): raise ValueError("invalid pronunciation test")
                self._json(HTTPStatus.OK, {"display_text": text, "tts_text": repository.apply_pronunciation(text, character_id)}); return
            if path.startswith("/api/voice/artifacts/"):
                if not self.server.voice: raise VoiceUnavailable("Voice unavailable")
                suffix = path.removeprefix("/api/voice/artifacts/")
                if "/" not in suffix: self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
                artifact_id, action = suffix.split("/", 1)
                if action == "favorite":
                    favorite = payload.get("favorite")
                    if not isinstance(favorite, bool): raise ValueError("invalid favorite")
                    self._json(HTTPStatus.OK, self.server.voice.set_favorite(artifact_id, favorite)); return
                if action == "retry":
                    self._json(HTTPStatus.CREATED, self.server.voice.retry_artifact(artifact_id, session_id)); return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
            if path == "/api/assistant":
                message, context = payload.get("message"), payload.get("context", {})
                if not isinstance(message, str) or not message.strip() or len(message) > 4000 or not isinstance(context, dict): raise ValueError("invalid assistant request")
                allowed_context = {key: str(value)[:120] for key, value in context.items() if key in {"page", "selected_voice_model", "selected_style", "subsystem_status"} and isinstance(value, (str, int, float, bool))}
                assistant_session = "workspace-assistant-shion"
                if self.server.controller.conversations:
                    try: self.server.controller.conversations.load_session(assistant_session)
                    except KeyError: self.server.controller.create_persistent_session(assistant_session, "minimal")
                structured = f"[Workspace context: {json.dumps(allowed_context, ensure_ascii=False)}]\n{message.strip()}"
                result = self.server.controller.chat(assistant_session, "minimal", structured)
                self._json(HTTPStatus.OK, result); return
            if path == "/api/regenerate":
                mode = payload.get("mode")
                if mode not in {"minimal", "neutral", "canonical"}:
                    raise ValueError("invalid mode")
                message_id = payload.get("message_id")
                if message_id is not None and (not isinstance(message_id, str) or not message_id.isascii()): raise ValueError("invalid message_id")
                self._json(HTTPStatus.OK, self.server.controller.regenerate(session_id, mode, message_id))
                return
            if path == "/api/response/select":
                mode, response = payload.get("mode"), payload.get("response")
                if mode not in {"minimal", "neutral", "canonical"} or not isinstance(response, str):
                    raise ValueError("invalid response selection")
                self.server.controller.select_response(session_id, mode, response)
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/model":
                alias = payload.get("model_alias")
                if not isinstance(alias, str):
                    raise ValueError("model_alias required")
                self.server.controller.switch(self.server.common_path, alias, session_id)
                self._json(HTTPStatus.ACCEPTED, {"ok": True, "state": self.server.controller.state})
                return
            if path != "/api/chat":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            message = payload.get("message")
            mode = payload.get("mode")
            if not isinstance(message, str) or not message.strip() or len(message) > 20_000:
                raise ValueError("message must contain 1-20000 characters")
            if mode not in {"minimal", "neutral", "canonical"}:
                raise ValueError("invalid mode")
            result = self.server.controller.chat(session_id, mode, message.strip())
            self._json(HTTPStatus.OK, result)
        except OverflowError as error:
            self._json(HTTPStatus.CONFLICT, {"error": str(error)})
        except ResourceGateFull as error:
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(error), "state": "WAITING_FOR_GPU"})
        except ResourceGateTimeout as error:
            self._json(HTTPStatus.GATEWAY_TIMEOUT, {"error": str(error), "state": "WAITING_FOR_GPU"})
        except ResourceGateCancelled as error:
            self._json(HTTPStatus.CONFLICT, {"error": str(error), "state": "CANCELLED"})
        except VoiceUnavailable as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": f"Voice unavailable: {error}"})
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Record not found"})
        except SensitiveMemoryError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except RuntimeError:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "モデルはまだ準備中です。"})
        except (ValueError, json.JSONDecodeError) as error:
            LOG.warning("Request validation failed: %s", error)
            self._json(HTTPStatus.BAD_REQUEST, {"error": "リクエストを確認してください。"})
        except Exception:
            LOG.error("Request failed\n%s", traceback.format_exc())
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "モデルの応答生成に失敗しました。"})


    def do_PATCH(self) -> None:
        if not self._allowed_host(): self._json(HTTPStatus.FORBIDDEN, {"error": "localhost access only"}); return
        try:
            payload = self._read_json(); session_id = payload.pop("session_id", None)
            if not isinstance(session_id, str) or not 8 <= len(session_id) <= 80 or not session_id.isascii(): raise ValueError("invalid session_id")
            path = urlparse(self.path).path
            if path.startswith("/api/voice/pronunciations/"):
                repository = self.server.controller.conversations
                if not repository: raise RuntimeError("persistent history unavailable")
                self._json(HTTPStatus.OK, repository.update_pronunciation_rule(path.removeprefix("/api/voice/pronunciations/"), payload)); return
            if not path.startswith("/api/memory/"): self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
            memory = self.server.controller.orchestrator.long_term_memory
            if not memory.available: raise RuntimeError("Memory unavailable")
            self._json(HTTPStatus.OK, memory.update(path.removeprefix("/api/memory/"), payload))
        except KeyError: self._json(HTTPStatus.NOT_FOUND, {"error": "Record not found"})
        except SensitiveMemoryError as error: self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except (ValueError, json.JSONDecodeError): self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Memory request"})
        except Exception:
            LOG.error("Memory update failed\n%s", traceback.format_exc()); self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Memory update unavailable"})

    def do_DELETE(self) -> None:
        if not self._allowed_host(): self._json(HTTPStatus.FORBIDDEN, {"error": "localhost access only"}); return
        try:
            payload = self._read_json(); session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not 8 <= len(session_id) <= 80 or not session_id.isascii(): raise ValueError("invalid session_id")
            if payload.get("confirm") != "DELETE": raise ValueError("hard delete confirmation required")
            path = urlparse(self.path).path
            if path.startswith("/api/voice/pronunciations/"):
                repository = self.server.controller.conversations
                if not repository: raise RuntimeError("persistent history unavailable")
                repository.delete_pronunciation_rule(path.removeprefix("/api/voice/pronunciations/")); self._json(HTTPStatus.OK, {"ok": True, "deleted": True}); return
            if path.startswith("/api/voice/artifacts/"):
                if not self.server.voice: raise VoiceUnavailable("Voice unavailable")
                self._json(HTTPStatus.OK, self.server.voice.delete_artifact(path.removeprefix("/api/voice/artifacts/"))); return
            if not path.startswith("/api/memory/"): self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
            memory = self.server.controller.orchestrator.long_term_memory
            if not memory.available: raise RuntimeError("Memory unavailable")
            memory.delete(path.removeprefix("/api/memory/")); self._json(HTTPStatus.OK, {"ok": True, "deleted": True})
        except KeyError: self._json(HTTPStatus.NOT_FOUND, {"error": "Record not found"})
        except (ValueError, json.JSONDecodeError): self._json(HTTPStatus.BAD_REQUEST, {"error": "Hard delete confirmation required"})
        except Exception:
            LOG.error("Memory delete failed\n%s", traceback.format_exc()); self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "Memory delete unavailable"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Localhost-only SHION web chat")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--common", type=Path, default=Path("training/configs/common.yaml"))
    parser.add_argument("--model", default="gemma4_12b_heretic_ja_v2_manual", help="Server-side allowlisted model alias")
    parser.add_argument("--adapter", type=Path)
    return parser


def create_server(host: str, port: int, controller: RuntimeController, common_path: Path = Path("training/configs/common.yaml"), tailscale_hosts: set[str] | None = None, voice: VoiceServiceClient | None = None) -> ShionServer:
    if host != "127.0.0.1":
        raise ValueError("only 127.0.0.1 is permitted")
    server = ShionServer((host, port), Handler)
    server.controller = controller
    server.gpu_gate = GpuResourceGate(lambda: str(controller.state) == "Ready")
    controller.gpu_gate = server.gpu_gate
    server.common_path = common_path
    server.tailscale_hosts = frozenset(discover_tailscale_hosts() if tailscale_hosts is None else tailscale_hosts)
    server.voice = voice
    if voice:
        voice.gpu_gate = server.gpu_gate
    server.characters = CharacterRegistry(CHARACTER_ROOT)
    server.storage_root = Path(os.environ.get("SHION_DATA_ROOT", r"D:\AI\Project_SHION"))
    def system_snapshot() -> dict:
        memory = {"state": "UNAVAILABLE"}
        try:
            import psutil
            vm = psutil.virtual_memory(); memory = {"state": "AVAILABLE", "total_mib": round(vm.total / 2**20), "available_mib": round(vm.available / 2**20), "percent": vm.percent}
        except Exception: pass
        gpu = {"state": "UNAVAILABLE"}
        try:
            query = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            name, total, used, free = [item.strip() for item in query.stdout.splitlines()[0].split(",")]
            gpu = {"state": "AVAILABLE", "name": name, "total_mib": int(total), "used_mib": int(used), "free_mib": int(free)}
        except Exception: pass
        disk = shutil.disk_usage(server.storage_root.anchor or server.storage_root)
        repository = controller.conversations
        memory_backend = controller.orchestrator.long_term_memory
        memory_status = {"state": "READY" if memory_backend.available else "DISABLED",
                         "automatic_promotion": False, "error": getattr(memory_backend, "last_error", None)}
        return {"server": {"state": str(controller.state), "bind": "loopback-only"}, "conversation": controller.status().get("history", {}),
                "voice": voice.status() if voice else {"state": "UNAVAILABLE"}, "image": {"state": "NOT_INTEGRATED"}, "memory": memory_status,
                "model": {"alias": controller.current_alias}, "sqlite": repository.integrity_status() if repository else {"state": "UNAVAILABLE"},
                "ram": memory, "gpu": gpu, "storage": {"free_gib": round(disk.free / 2**30, 1), "total_gib": round(disk.total / 2**30, 1)},
                "processes": {"shion_server": "RUNNING", "voice_service": voice.status().get("state") if voice else "UNAVAILABLE"}}
    server.system_snapshot = system_snapshot
    return server


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = StoragePaths.resolve()
    paths.create_runtime_dirs()
    conversations = ConversationRepository(paths.conversation_db, enabled=True)
    try:
        conversations.migrate()
        controller = RuntimeController(conversations=conversations)
    except Exception as error:
        LOG.error("Conversation DB unavailable; explicit ephemeral fallback enabled: %s", error)
        controller = RuntimeController()
        controller.persistence_error = str(error)
    try:
        # Bind before model load: the OS lock is race-safe and prevents a duplicate
        # process from allocating model RAM only to fail on port 8765 afterward.
        voice = VoiceServiceClient(paths.root, ROOT, conversations) if controller.conversations else None
        server = create_server(args.host, args.port, controller, args.common, voice=voice)
    except OSError as error:
        raise SystemExit(f"SHION server startup rejected before model load: {error}") from error
    controller.load(args.common, args.model, args.adapter)
    LOG.info("SHION Web Chat: http://%s:%s", args.host, args.port)
    LOG.info("Loopback bind enforced; allowed Tailscale Serve hosts: %s", sorted(server.tailscale_hosts))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Stopping")
    finally:
        server.server_close()
        if server.voice: server.voice.close()
        controller.close()


if __name__ == "__main__":
    main()
