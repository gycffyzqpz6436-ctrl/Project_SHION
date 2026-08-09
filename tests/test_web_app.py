import http.client
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.server import RuntimeController, create_server


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

    def request(self, method, path, payload=None, host="127.0.0.1"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Host": host}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, response.getheader("Content-Security-Policy"), data

    def test_static_and_status(self):
        status, csp, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"SHION Local Chat", body)
        self.assertIn("default-src 'self'", csp)
        status, _, body = self.request("GET", "/api/status")
        payload = json.loads(body)
        self.assertEqual(payload["state"], "Ready")
        self.assertNotIn("local_path", json.dumps(payload))

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

    def test_neutral_conversation_mode_is_accepted(self):
        session = "session-neutral"
        status, _, body = self.request("POST", "/api/chat", {"session_id": session, "mode": "neutral", "message": "hello"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["response"], "reply: hello")
        self.assertIn((session, "neutral"), self.controller.histories)

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

    def test_model_switch_releases_old_runtime_and_resets_history(self):
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


if __name__ == "__main__":
    unittest.main()
