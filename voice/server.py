from __future__ import annotations

import argparse
import json
import mimetypes
import os
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


VOICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(VOICE_DIR))
sys.path.insert(0, str(VOICE_DIR / "scripts"))

from controller import OUTPUT_DIR, VoiceController, VoiceSettings  # noqa: E402
from model_manager import SavedRevisionUnavailable  # noqa: E402


STATIC_DIR = VOICE_DIR / "static"
MAX_REQUEST_BYTES = 32 * 1024


class VoiceHandler(BaseHTTPRequestHandler):
    controller: VoiceController

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Invalid request size")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/meta":
            self._send_json({**self.controller.metadata(), "presets": self.controller.list_presets(), "managed_models": self.controller.models.list_models(), "huggingface": self.controller.models.huggingface_status()})
            return
        if path.startswith("/audio/"):
            name = Path(unquote(path.removeprefix("/audio/"))).name
            target = OUTPUT_DIR / name
            if not target.is_file() or target.suffix.lower() != ".wav":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        target = STATIC_DIR / ("index.html" if path == "/" else Path(path).name)
        if not target.is_file() or target.parent != STATIC_DIR:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._body()
            if self.path == "/api/generate":
                settings = VoiceSettings.from_payload(payload)
                self._send_json(self.controller.generate(settings))
            elif self.path in ("/api/presets/candidate", "/api/presets/approve"):
                settings = VoiceSettings.from_payload(payload)
                result = self.controller.save_preset(
                    settings, str(payload.get("preset_name", "")), self.path.endswith("approve")
                )
                self._send_json(result, 201)
            elif self.path == "/api/models/refresh":
                self._send_json({"models": self.controller.models.refresh(), **self.controller.metadata()})
            elif self.path == "/api/models/local":
                self._send_json(self.controller.models.register_local(str(payload.get("path", "")), str(payload.get("display_name", ""))))
            elif self.path == "/api/models/flags":
                allowed = {key: payload[key] for key in ("enabled", "removed", "license_reviewed") if key in payload}
                self._send_json(self.controller.models.set_flags(str(payload.get("model_id", "")), **allowed))
            elif self.path == "/api/models/test":
                self._send_json(self.controller.test_model(str(payload.get("model_id", "")), str(payload.get("text") or "……聞こえる？ お兄さん♪")))
            elif self.path == "/api/models/hf-preview":
                self._send_json(self.controller.models.preview_huggingface(str(payload.get("repo_id", "")), str(payload.get("revision", ""))))
            elif self.path == "/api/models/hf-refresh-revision":
                self._send_json(self.controller.models.refresh_huggingface_revision(str(payload.get("repo_id", ""))))
            elif self.path == "/api/models/hf-download":
                self._send_json(self.controller.models.download_huggingface(str(payload.get("repo_id", "")), str(payload.get("revision", "")), str(payload.get("candidate", ""))))
            elif self.path == "/api/models/open":
                record = self.controller.models.get(str(payload.get("model_id", "")), allow_unready=True)
                os.startfile(record.local_path)  # type: ignore[attr-defined]
                self._send_json({"opened": str(record.local_path)})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except SavedRevisionUnavailable as exc:
            self._send_json({"error": "Saved revision is no longer available.", "code": "saved_revision_unavailable", "repo_id": exc.repo_id, "revision": exc.revision, "actions": ["refresh_repository_revision", "cancel"]}, 409)
        except FileExistsError as exc:
            self._send_json({"error": str(exc)}, 409)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:
            if type(exc).__name__ == "OfflineModeIsEnabled":
                self._send_json({"error": "Hugging Face offline mode is enabled"}, 503)
            else:
                self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {fmt % args}")


def create_server(port: int = 8766) -> ThreadingHTTPServer:
    VoiceHandler.controller = VoiceController()
    return ThreadingHTTPServer(("127.0.0.1", port), VoiceHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="SHION Voice Tuning Console")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = create_server(args.port)
    print(f"SHION Voice Tuning Console: http://127.0.0.1:{server.server_port}")
    print("Localhost-only binding is enforced.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
