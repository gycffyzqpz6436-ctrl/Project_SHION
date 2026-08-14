import http.client
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.shion_runtime import conversation_title
from app.server import RuntimeController, build_parser, create_server


class FakeRuntime:
    def status(self):
        return {"model": "approved-model", "adapter": "none", "context_limit": 100, "generation": {}, "gpu_memory_allocated_mib": 1, "gpu_memory_reserved_mib": 2}

    def generate(self, session_id, mode, history, message):
        return f"reply: {message}", 12

    def reset(self, session_id):
        pass

    def cancel(self, session_id):
        return True


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = RuntimeController()
        cls.controller.runtime = FakeRuntime()
        cls.controller.state = "Ready"
        cls.server = create_server("127.0.0.1", 0, cls.controller)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, payload=None, host="127.0.0.1", extra_headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Host": host}
        if body is not None:
            headers["Content-Type"] = "application/json"
        headers.update(extra_headers or {})
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, response.getheader("Content-Security-Policy"), data

    def test_static_and_status(self):
        status, csp, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Project SHION", body)
        self.assertIn("default-src 'self'", csp)
        status, _, body = self.request("GET", "/api/status")
        payload = json.loads(body)
        self.assertEqual(payload["state"], "Ready")
        self.assertNotIn("local_path", json.dumps(payload))
        status, _, body = self.request("GET", "/assets/characters/shion/profile.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["renderer"]["asset_set"], "official_static_2d_v1")
        status, _, body = self.request("GET", "/assets/characters/shion/official/static_2d/shion_avatar.png")
        self.assertEqual(status, 200)
        self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")
        status, _, _ = self.request("GET", "/assets/characters/../../model_registry.json")
        self.assertEqual(status, 404)
        status, _, body = self.request("GET", "/api/characters/shion")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["default_voice"]["style"], "Bright")
        status, _, body = self.request("GET", "/api/dashboard")
        self.assertEqual(status, 200)
        dashboard = json.loads(body)
        self.assertEqual(dashboard["character"]["character_id"], "shion")
        self.assertNotIn("system", dashboard)
        status, _, body = self.request("GET", "/api/system")
        self.assertEqual(status, 200)
        self.assertNotIn("D:\\", body.decode())

    def test_chat_reset_and_schema(self):
        session = "session-1234"
        status, _, body = self.request("POST", "/api/chat", {"session_id": session, "mode": "minimal", "message": "こんにちは"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["response"], "reply: こんにちは")
        self.assertEqual(len(self.controller.histories[(session, "minimal")]), 2)
        status, _, _ = self.request("POST", "/api/reset", {"session_id": session})
        self.assertEqual(status, 200)
        self.assertNotIn((session, "minimal"), self.controller.histories)
        status, _, _ = self.request("POST", "/api/chat", {"session_id": session, "mode": "bad", "message": "x"})
        self.assertEqual(status, 400)

    def test_response_metadata_and_regenerate(self):
        session = "session-regenerate"
        status, _, body = self.request(
            "POST", "/api/chat",
            {"session_id": session, "mode": "minimal", "message": "again"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("message_id", payload)
        self.assertIn("created_at", payload)
        self.assertIn("latency_ms", payload["generation"])
        status, _, body = self.request(
            "POST", "/api/regenerate",
            {"session_id": session, "mode": "minimal"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["response"], "reply: again")
        self.assertEqual(len(self.controller.histories[(session, "minimal")]), 2)
        status, _, _ = self.request("POST", "/api/response/select", {"session_id": session, "mode": "minimal", "response": "selected"})
        self.assertEqual(status, 200)
        self.assertEqual(self.controller.histories[(session, "minimal")][-1]["content"], "selected")

    def test_neutral_conversation_mode_is_accepted(self):
        session = "session-neutral"
        status, _, body = self.request("POST", "/api/chat", {"session_id": session, "mode": "neutral", "message": "hello"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["response"], "reply: hello")
        self.assertIn((session, "neutral"), self.controller.histories)

    def test_floating_assistant_accepts_only_bounded_workspace_context(self):
        status, _, body = self.request("POST", "/api/assistant", {"session_id": "workspace-assistant-shion", "message": "help", "context": {"page": "voice", "credential": "secret", "filesystem": "D:/private"}})
        self.assertEqual(status, 200)
        self.assertNotIn("secret", body.decode())

    def test_stop_generation_endpoint_requests_safe_cancel(self):
        session = "session-stop"
        self.controller.state = "Generating"
        status, _, body = self.request("POST", "/api/stop", {"session_id": session})
        self.assertEqual(status, 202)
        self.assertTrue(json.loads(body)["stop_requested"])
        self.controller.state = "Ready"

    def test_rejects_non_local_host_header(self):
        status, _, _ = self.request("GET", "/api/status", host="example.com")
        self.assertEqual(status, 403)

    def test_allows_exact_tailscale_serve_proxy_boundary(self):
        self.server.tailscale_hosts = frozenset({"pc", "pc.example.ts.net"})
        headers = {
            "Tailscale-User-Login": "owner@example.com",
            "Origin": "http://pc:8080",
            "X-Forwarded-Proto": "http",
        }
        status, _, body = self.request("GET", "/api/status", host="pc:8080", extra_headers=headers)
        self.assertEqual(status, 200, body)
        headers["Origin"] = "http://evil.example"
        status, _, _ = self.request("GET", "/api/status", host="pc:8080", extra_headers=headers)
        self.assertEqual(status, 403)

    def test_rejects_spoofed_or_unapproved_proxy_hosts(self):
        self.server.tailscale_hosts = frozenset({"pc", "pc.example.ts.net"})
        status, _, _ = self.request("GET", "/api/status", host="pc:8080")
        self.assertEqual(status, 403)
        status, _, _ = self.request(
            "GET", "/api/status", host="192.168.0.9:8765",
            extra_headers={"Tailscale-User-Login": "owner@example.com"},
        )
        self.assertEqual(status, 403)

    def test_safe_diagnostics_header_allowlist_excludes_secrets(self):
        from app.server import Handler
        handler = object.__new__(Handler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.headers = {
            "Host": "pc:8080", "Origin": "http://pc:8080", "Tailscale-User-Login": "owner@example.com",
            "Authorization": "Bearer secret", "Cookie": "session=secret", "X-Api-Key": "secret",
        }
        diagnostics = handler._safe_request_diagnostics()
        serialized = json.dumps(diagnostics)
        self.assertIn("Tailscale-User-Login", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Cookie", serialized)
        self.assertNotIn("secret", serialized)

    def test_rejects_unavailable_and_arbitrary_model_alias(self):
        session = "session-5678"
        for alias in (
            "heretic7b_experimental",
            "impish_nemo12b_experimental",
            "lumimaid12b_experimental",
            "shisa_v2_nemo12b_experimental",
            "D:/arbitrary/model",
        ):
            status, _, _ = self.request("POST", "/api/model", {"session_id": session, "model_alias": alias})
            self.assertEqual(status, 400)

    def test_bind_is_locked_to_loopback(self):
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            create_server("0.0.0.0", 0, RuntimeController())
        self.assertFalse(type(self.server).allow_reuse_address)

    def test_model_switch_releases_old_runtime_and_preserves_other_sessions(self):
        registry = {"next": {"available": True, "display_name": "Next", "repo_id": "owner/repo", "revision": "abc", "parent_model": "parent", "provenance": "Official", "modification_type": "test", "parameter_scale": "1B"}}
        controller = RuntimeController(registry)
        old = Mock()
        controller.runtime = old
        controller.state = "Ready"
        controller.current_alias = "old"
        controller.histories[("session-1234", "minimal")] = [{"role": "user", "content": "x"}]
        replacement = Mock()
        with patch("app.server.LocalModelRuntime", return_value=replacement):
            controller.switch(Path("common.yaml"), "next", "session-1234")
            for _ in range(100):
                if controller.state in {"Ready", "Error"}:
                    break
                time.sleep(0.01)
        self.assertEqual(controller.state, "Ready")
        self.assertIs(controller.runtime, replacement)
        old.close.assert_called_once()
        self.assertIn(("session-1234", "minimal"), controller.histories)

    def test_runtime_close_releases_model_and_sessions(self):
        controller = RuntimeController()
        runtime = Mock()
        controller.runtime = runtime
        controller.current_alias = "model"
        controller.histories[("session", "minimal")] = [{"role": "user", "content": "x"}]
        controller.close()
        runtime.close.assert_called_once()
        self.assertIsNone(controller.runtime)
        self.assertEqual(controller.histories, {})

    def test_frontend_is_local_and_responsive(self):
        static = Path(__file__).resolve().parents[1] / "app" / "static"
        combined = "\n".join(path.read_text(encoding="utf-8") for path in static.iterdir() if path.is_file())
        self.assertNotIn("https://", combined)
        self.assertNotIn("http://", combined)
        self.assertIn("@media(max-width:640px)", combined)
        self.assertIn("event.shiftKey", combined)
        self.assertIn("overflow:auto", combined)
        self.assertIn("escapeHtml", combined)
        self.assertIn('id="model"', combined)
        self.assertIn('value="neutral"', combined)
        self.assertIn("Base origin:", combined)
        self.assertIn("/api/model", combined)
        self.assertIn("/api/stop", combined)
        self.assertIn("Model Info", combined)
        self.assertIn("Personal AI Companion", combined)
        self.assertIn("composer-slots", combined)
        self.assertIn("createSessionId", combined)
        self.assertIn("crypto?.getRandomValues", combined)
        self.assertIn("Initialization failed", combined)
        self.assertIn("if (!response.ok)", combined)
        self.assertIn("shion-ephemeral-sessions:v1", combined)
        self.assertIn("sessionStorage", combined)
        self.assertNotIn("localStorage", combined)
        self.assertIn("SHION Default", combined)
        self.assertIn("Nene V3", combined)
        self.assertIn('id="voice-developer" type="checkbox"', combined)
        self.assertNotIn('id="voice-developer" type="checkbox" checked', combined)
        self.assertIn("Voice presetを選択してください。", combined)
        self.assertIn('selection === "model:F1"', combined)
        self.assertIn('ui.voiceStatus.textContent = "Voice WAITING_FOR_GPU"', combined)
        self.assertNotIn('new Option("SHION Default"', combined)
        self.assertIn("activeSessionId", combined)
        self.assertIn("session-list", combined)
        self.assertIn('data-route="chat"', combined)
        self.assertIn("Coming Soon", combined)
        self.assertIn("archive-dialog", combined)
        self.assertIn("/api/sessions/archive", combined)
        self.assertIn("typewriterText", combined)
        self.assertIn("prefers-reduced-motion", combined)
        self.assertIn("character-renderer", combined)
        self.assertIn("mobile-nav-toggle", combined)
        self.assertIn("safe-area-inset-bottom", combined)
        self.assertIn("loadCharacterProfile", combined)
        self.assertIn("resolveCharacterAsset", combined)
        self.assertIn('data-character-asset="panel"', combined)
        self.assertIn("renderHomePage", combined)
        self.assertIn("renderVoiceLabPage", combined)
        self.assertIn("Retry current settings", combined)
        self.assertIn("GPU VRAM", combined)
        self.assertIn("floating-assistant", combined)
        self.assertIn("Dictionary persistence: Owner Gate", combined)
        self.assertIn("session-menu-popover", combined)
        self.assertIn("autoFollow", combined)
        self.assertIn('enter_behavior: "desktop-send"', combined)
        self.assertIn("renderMemoryPage", combined)
        self.assertIn("renderSettingsPage", combined)
        self.assertIn("SHION THINKING", combined)
        self.assertIn("layout-force-mobile", combined)
        self.assertIn("WAITING_FOR_GPU", combined)
        self.assertIn("/api/voice/queue/cancel", combined)
        self.assertIn("if (ui.voiceAutoplay.checked) generateVoice", combined)

    def test_workspace_defaults_and_deterministic_title(self):
        self.assertEqual(build_parser().parse_args([]).model, "gemma4_12b_heretic_ja_v2_manual")
        self.assertEqual(conversation_title("Nene音声調整について相談したい。"), "Neneの音声調整")
        self.assertEqual(conversation_title("今日ちょっと聞きたいんだけど紫苑ちゃんの声を調整したい。"), "紫苑の音声調整")
        self.assertEqual(conversation_title("香港出張の準備と予定を整理したい。"), "香港出張の準備")
        self.assertEqual(conversation_title("SHION UI改修を進めたい。"), "SHION UI改修")


if __name__ == "__main__":
    unittest.main()
