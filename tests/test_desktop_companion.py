import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from desktop_companion.app import clamp_position
from desktop_companion.backend import BackendClient, BackendOffline
from desktop_companion.renderer import CharacterRenderer, Static2DAsset
from desktop_companion.settings import CompanionSettings, SettingsStore
from desktop_companion.startup import StartupRegistration
from desktop_companion.tray import WindowsTray


ROOT = Path(__file__).resolve().parents[1]


class CompanionApiHandler(BaseHTTPRequestHandler):
    sessions = [{"session_id": "shared-session", "title": "Shared SHION", "character_id": "shion"}]

    def log_message(self, *_args): pass

    def _json(self, status, payload):
        body = json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            self._json(200, {"state": "Ready", "voice": {"resource_gate": {"state": "READY", "llm_active": False}}})
        elif self.path == "/api/sessions": self._json(200, {"sessions": self.sessions})
        elif self.path == "/api/sessions/shared-session":
            self._json(200, {"session_id": "shared-session", "character_id": "shion", "messages": [{"role": "user", "parts": [{"type": "text", "text": "web and desktop"}]}]})
        elif self.path == "/api/voice/artifacts/artifact-id":
            body = b"RIFF" + b"\0" * 20; self.send_response(200); self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        else: self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0)); payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/sessions": self._json(201, {"session_id": payload["session_id"], "character_id": "shion"})
        elif self.path == "/api/chat":
            self._json(200, {"response": "same backend", "session_id": payload["session_id"], "message_id": "message-id", "version": 1})
        elif self.path == "/api/voice/generate":
            self._json(201, {"audio_url": "/api/voice/artifacts/artifact-id", "voice_preset_id": payload["preset_id"]})
        else: self._json(404, {"error": "not found"})


class DesktopCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), CompanionApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.client = BackendClient(f"http://127.0.0.1:{cls.server.server_address[1]}")

    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close()

    def test_settings_persist_and_startup_defaults_off(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory)); settings = CompanionSettings(x=-600, y=90, session_id="shared-session")
            store.save(settings); restored = store.load()
            self.assertEqual((restored.x, restored.y, restored.session_id), (-600, 90, "shared-session"))
            self.assertFalse(restored.start_with_windows)
            self.assertFalse(StartupRegistration(ROOT / "Start-SHION-Companion.ps1").command.startswith(str(ROOT)))

    def test_corrupt_settings_and_invalid_values_recover(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory)); store.path.parent.mkdir(parents=True)
            store.path.write_text('{"x":"bad","scale":9,"start_with_windows":"yes"}', encoding="utf-8")
            settings = store.load()
            self.assertEqual((settings.x, settings.y, settings.scale), (80, 80, .34))
            self.assertFalse(settings.start_with_windows)

    def test_position_recovery_keeps_character_visible_across_virtual_monitors(self):
        self.assertEqual(clamp_position(9000, 9000, 400, 600, (-1920, 0, 3840, 1080)), (1824, 984))
        self.assertEqual(clamp_position(-9000, -50, 400, 600, (-1920, 0, 3840, 1080)), (-2224, 0))

    def test_backend_connect_reconnect_and_shared_conversation(self):
        self.assertEqual(self.client.state(self.client.status()), "IDLE")
        self.assertEqual(self.client.sessions()[0]["character_id"], "shion")
        self.assertEqual(self.client.load_session("shared-session")["messages"][0]["parts"][0]["text"], "web and desktop")
        self.assertEqual(self.client.chat("shared-session", "continue")["response"], "same backend")

    def test_voice_uses_existing_backend_preset_and_artifact(self):
        voice = self.client.generate_voice("shared-session", "message-id")
        self.assertEqual(voice["voice_preset_id"], "SHION Default")
        self.assertTrue(self.client.audio(voice["audio_url"]).startswith(b"RIFF"))

    def test_gpu_and_offline_states(self):
        self.assertEqual(BackendClient.state({"state": "Generating", "voice": {"resource_gate": {"state": "READY"}}}), "GENERATING")
        self.assertEqual(BackendClient.state({"state": "Ready", "voice": {"resource_gate": {"state": "WAITING_FOR_GPU"}}}), "WAITING_FOR_GPU")
        with self.assertRaises(BackendOffline): BackendClient("http://127.0.0.1:1", timeout=.05).status()

    def test_backend_rejects_non_loopback_and_unsafe_audio(self):
        with self.assertRaises(ValueError): BackendClient("http://192.168.1.20:8765")
        with self.assertRaises(ValueError): self.client.audio("http://example.com/file.wav")

    def test_official_static_asset_is_manifest_resolved_without_derivative(self):
        asset = Static2DAsset(ROOT)
        self.assertEqual(asset.character_id, "shion"); self.assertEqual(asset.role, "panel")
        self.assertEqual(asset.path.name, "shion_panel.png"); self.assertTrue(asset.manifest["owner_approved"])

    def test_renderer_boundary_and_tray_actions_exist(self):
        self.assertTrue(CharacterRenderer.__abstractmethods__.issuperset({"set_character", "set_state", "set_scale", "show", "hide"}))
        self.assertEqual({WindowsTray.ID_SHOW, WindowsTray.ID_HIDE, WindowsTray.ID_WEB, WindowsTray.ID_TOP,
                          WindowsTray.ID_STARTUP, WindowsTray.ID_EXIT}, set(range(1001, 1007)))

    def test_security_boundary_has_no_surveillance_dependencies(self):
        sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "desktop_companion").glob("*.py"))
        for forbidden in ("pyautogui", "pynput", "ImageGrab", "GetClipboardData", "sounddevice", "microphone"):
            self.assertNotIn(forbidden, sources)
        self.assertNotIn("from app.runtime", sources); self.assertNotIn("ConversationRepository", sources)


if __name__ == "__main__": unittest.main()
