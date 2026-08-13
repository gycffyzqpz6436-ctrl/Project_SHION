import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


VOICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VOICE_DIR))
sys.path.insert(0, str(VOICE_DIR / "scripts"))

import controller
import model_manager
import server


def valid_payload() -> dict:
    return {
        "text": "テストです。",
        "voice_model": "F1",
        "style": "Neutral",
        "style_weight": 1.0,
        "length": 1.0,
        "pitch_scale": 1.0,
        "intonation_scale": 1.0,
        "sdp_ratio": 0.2,
        "noise": 0.6,
        "noise_w": 0.8,
        "assist_text": "",
        "assist_text_weight": 0.7,
    }


class VoiceConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.patchers = [
            patch.object(model_manager, "VOICE_ROOT", root),
            patch.object(model_manager, "MODELS_ROOT", root / "models"),
            patch.object(model_manager, "REGISTRY_PATH", root / "data" / "models.json"),
            patch.object(model_manager, "TEMP_ROOT", root / "temp"),
            patch.object(model_manager, "HF_CACHE", root / "cache"),
            patch.object(model_manager, "KNOWN_MODELS", {}),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def test_shion_default_preset_is_owner_approved_nene_bright(self) -> None:
        preset = json.loads((VOICE_DIR / "presets" / "approved" / "SHION_Default.json").read_text(encoding="utf-8"))
        self.assertEqual(preset["preset_name"], "SHION Default")
        self.assertEqual(preset["status"], "approved")
        self.assertTrue(preset["approved"])
        self.assertTrue(preset["owner_approved"])
        self.assertEqual(preset["voice_model"], "nene_v3_candidate")
        self.assertEqual(preset["style"], "Bright")

    def test_parameter_limits_reject_extreme_pitch(self) -> None:
        payload = valid_payload()
        payload["pitch_scale"] = 3.0
        with self.assertRaisesRegex(ValueError, "pitch_scale"):
            controller.VoiceSettings.from_payload(payload)

    def test_server_is_localhost_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(controller, "OUTPUT_DIR", Path(temporary)):
            httpd = server.create_server(0)
            try:
                self.assertEqual(httpd.server_address[0], "127.0.0.1")
            finally:
                httpd.server_close()

    def test_candidate_and_approval_are_separate_and_reloadable(self) -> None:
        settings = controller.VoiceSettings.from_payload(valid_payload())
        with tempfile.TemporaryDirectory() as temporary, patch.object(controller, "OUTPUT_DIR", Path(temporary) / "output"), patch.object(controller, "PRESET_DIR", Path(temporary) / "presets"):
            instance = controller.VoiceController()
            candidate = instance.save_preset(settings, "Shion_Test_Candidate", False)
            approved = instance.save_preset(settings, "Shion_Test_Approved", True)
            self.assertFalse(candidate["preset"]["owner_approved"])
            self.assertTrue(approved["preset"]["owner_approved"])
            reloaded = instance.list_presets()
            self.assertEqual({item["status"] for item in reloaded}, {"candidate", "approved"})
            self.assertEqual(json.loads(Path(approved["path"]).read_text(encoding="utf-8"))["voice_model"], "F1")


if __name__ == "__main__":
    unittest.main()
