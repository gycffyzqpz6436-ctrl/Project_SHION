"""Localhost-only HTTP server for the SHION web chat MVP."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.model_runtime import LocalModelRuntime  # noqa: E402


STATIC = Path(__file__).resolve().parent / "static"
REGISTRY_PATH = Path(__file__).resolve().parent / "model_registry.json"
MAX_BODY_BYTES = 128 * 1024
LOG = logging.getLogger("shion_web")


class RuntimeController:
    def __init__(self, registry: dict | None = None) -> None:
        self.state = "Starting"
        self.runtime = None
        self.registry = registry if registry is not None else json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.current_alias = None
        self.histories: dict[tuple[str, str], list[dict]] = {}
        self.state_lock = threading.Lock()

    def public_models(self) -> list[dict]:
        safe_keys = ("display_name", "repo_id", "revision", "parent_model", "provenance", "modification_type", "parameter_scale", "available", "unavailable_reason")
        return [{"alias": alias, **{key: spec[key] for key in safe_keys if key in spec}} for alias, spec in self.registry.items()]

    def load(self, common: Path, alias: str, adapter: Path | None = None) -> None:
        spec = self.registry.get(alias)
        if spec is None or not spec.get("available"):
            raise ValueError("model alias is not available")
        self.state = "Loading model"

        def worker() -> None:
            try:
                old_runtime = self.runtime
                self.runtime = None
                if old_runtime is not None:
                    old_runtime.close()
                self.histories.clear()
                self.runtime = LocalModelRuntime(common, alias, spec, adapter)
                self.current_alias = alias
                self.state = "Ready"
            except Exception:
                self.state = "Error"
                LOG.error("Model loading failed\n%s", traceback.format_exc())

        threading.Thread(target=worker, name="model-loader", daemon=True).start()

    def status(self) -> dict:
        result = {"state": self.state, "models": self.public_models()}
        if self.runtime is not None:
            result.update(self.runtime.status())
        return result

    def chat(self, session_id: str, mode: str, message: str) -> dict:
        if self.state != "Ready" or self.runtime is None:
            raise RuntimeError("モデルはまだ準備中です。")
        key = (session_id, mode)
        history = self.histories.setdefault(key, [])
        self.state = "Generating"
        try:
            response, context_tokens = self.runtime.generate(session_id, mode, history, message)
            history.extend(({"role": "user", "content": message}, {"role": "assistant", "content": response}))
            return {"response": response, "context_tokens": context_tokens}
        finally:
            self.state = "Ready"

    def reset(self, session_id: str) -> None:
        for key in [key for key in self.histories if key[0] == session_id]:
            del self.histories[key]
        if self.runtime is not None:
            self.runtime.reset(session_id)

    def switch(self, common: Path, alias: str, session_id: str) -> None:
        with self.state_lock:
            if self.state != "Ready":
                raise RuntimeError("model is busy")
            if alias == self.current_alias:
                self.reset(session_id)
                return
            self.load(common, alias)


class ShionServer(ThreadingHTTPServer):
    controller: RuntimeController


class Handler(BaseHTTPRequestHandler):
    server: ShionServer

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _allowed_host(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        return host in {"127.0.0.1", "localhost"} and self.client_address[0] == "127.0.0.1"

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
        path = STATIC / name
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
            self._json(HTTPStatus.OK, self.server.controller.status())
        elif path in {"/", "/index.html"}:
            self._static("index.html", "text/html; charset=utf-8")
        elif path == "/app.js":
            self._static("app.js", "text/javascript; charset=utf-8")
        elif path == "/styles.css":
            self._static("styles.css", "text/css; charset=utf-8")
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
            if path == "/api/reset":
                self.server.controller.reset(session_id)
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
            if mode not in {"minimal", "canonical"}:
                raise ValueError("invalid mode")
            result = self.server.controller.chat(session_id, mode, message.strip())
            self._json(HTTPStatus.OK, result)
        except OverflowError as error:
            self._json(HTTPStatus.CONFLICT, {"error": str(error)})
        except RuntimeError:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "モデルはまだ準備中です。"})
        except (ValueError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "リクエストを確認してください。"})
        except Exception:
            LOG.error("Request failed\n%s", traceback.format_exc())
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "モデルの応答生成に失敗しました。"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Localhost-only SHION web chat")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--common", type=Path, default=Path("training/configs/common.yaml"))
    parser.add_argument("--model", default="ministral3_official", help="Server-side allowlisted model alias")
    parser.add_argument("--adapter", type=Path)
    return parser


def create_server(host: str, port: int, controller: RuntimeController, common_path: Path = Path("training/configs/common.yaml")) -> ShionServer:
    if host != "127.0.0.1":
        raise ValueError("only 127.0.0.1 is permitted")
    server = ShionServer((host, port), Handler)
    server.controller = controller
    server.common_path = common_path
    return server


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    controller = RuntimeController()
    server = create_server(args.host, args.port, controller, args.common)
    controller.load(args.common, args.model, args.adapter)
    LOG.info("SHION Web Chat: http://%s:%s", args.host, args.port)
    LOG.info("Localhost only; press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Stopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
