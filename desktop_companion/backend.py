from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid


class BackendOffline(ConnectionError):
    pass


class BackendClient:
    """Bounded localhost adapter; no model or persistence implementation lives here."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: float = 5.0) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Desktop Companion backend must be loopback-only")
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def request(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data,
            headers={"Content-Type": "application/json"} if data else {}, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try: detail = json.loads(error.read().decode("utf-8")).get("error", str(error))
            except Exception: detail = str(error)
            if error.code >= 500: raise BackendOffline(detail) from error
            raise ValueError(detail) from error
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            raise BackendOffline(str(error)) from error

    def status(self) -> dict:
        return self.request("/api/status")

    def sessions(self) -> list[dict]:
        return self.request("/api/sessions").get("sessions", [])

    def load_session(self, session_id: str) -> dict:
        return self.request(f"/api/sessions/{urllib.parse.quote(session_id, safe='')}")

    def create_session(self, mode: str = "neutral") -> dict:
        session_id = str(uuid.uuid4())
        return self.request("/api/sessions", {"session_id": session_id, "mode": mode})

    def chat(self, session_id: str, text: str, mode: str = "neutral") -> dict:
        if not text.strip() or len(text) > 20_000: raise ValueError("message must contain 1-20000 characters")
        return self.request("/api/chat", {"session_id": session_id, "mode": mode, "message": text.strip()}, timeout=240)

    def generate_voice(self, session_id: str, message_id: str, version: int = 1) -> dict:
        return self.request("/api/voice/generate", {"session_id": session_id, "message_id": message_id,
            "response_version": version, "preset_id": "SHION Default"}, timeout=240)

    def audio(self, audio_url: str) -> bytes:
        if not audio_url.startswith("/api/voice/artifacts/"): raise ValueError("unsafe audio URL")
        try:
            with urllib.request.urlopen(self.base_url + audio_url, timeout=30) as response:
                if response.headers.get_content_type() != "audio/wav": raise ValueError("unexpected audio response")
                return response.read(20 * 1024 * 1024 + 1)
        except (OSError, urllib.error.URLError) as error:
            raise BackendOffline(str(error)) from error

    @staticmethod
    def state(status: dict) -> str:
        voice = status.get("voice", {})
        gate = voice.get("resource_gate", {})
        if gate.get("state") == "WAITING_FOR_GPU": return "WAITING_FOR_GPU"
        runtime = str(status.get("state", "")).lower()
        if runtime == "generating" or gate.get("llm_active"): return "GENERATING"
        return "IDLE" if runtime == "ready" else "OFFLINE"
