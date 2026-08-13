import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


VOICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VOICE_DIR))

import model_manager
import hf_environment


def make_model(folder: Path, *, complete: bool = True) -> None:
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({"data": {"style2id": {"Neutral": 0, "Happy": 1}, "spk2id": {"Test Speaker": 0}}}), encoding="utf-8")
    if complete:
        (folder / "voice.safetensors").write_bytes(b"safe-test-weight")
        (folder / "style_vectors.npy").write_bytes(b"test-vectors")


class ModelManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.models = root / "models"
        self.registry = root / "registry" / "models.json"
        self.patchers = [
            patch.object(model_manager, "VOICE_ROOT", root), patch.object(model_manager, "MODELS_ROOT", self.models),
            patch.object(model_manager, "REGISTRY_PATH", self.registry), patch.object(model_manager, "TEMP_ROOT", root / "temp"),
            patch.object(model_manager, "HF_CACHE", root / "cache"), patch.object(model_manager, "KNOWN_MODELS", {}),
        ]
        for item in self.patchers: item.start()

    def tearDown(self) -> None:
        for item in reversed(self.patchers): item.stop()
        self.temporary.cleanup()

    def test_scan_ready_structure_starts_at_license_gate(self) -> None:
        make_model(self.models / "example" / "v1")
        manager = model_manager.VoiceModelManager()
        record = manager.list_models()[0]
        self.assertEqual(record["status"], "License Review Required")
        self.assertEqual(record["styles"], ["Neutral", "Happy"])

    def test_incomplete_model_is_not_ready(self) -> None:
        make_model(self.models / "broken", complete=False)
        record = model_manager.VoiceModelManager().list_models()[0]
        self.assertEqual(record["status"], "Incomplete")
        self.assertIn("model weight is missing", record["reasons"])

    def test_local_registration_enable_disable_and_restart_persistence(self) -> None:
        folder = self.models / "local" / "voice"
        make_model(folder)
        manager = model_manager.VoiceModelManager()
        record = manager.register_local(str(folder), "Local Voice")
        manager.set_flags(record["id"], license_reviewed=True, tested=True, enabled=False)
        restarted = model_manager.VoiceModelManager()
        disabled = restarted.get(record["id"], allow_unready=True)
        self.assertEqual(disabled.display_name, "Local Voice")
        self.assertEqual(disabled.status, "Disabled")
        restarted.set_flags(record["id"], enabled=True)
        self.assertEqual(restarted.get(record["id"]).status, "Ready")

    def test_path_outside_model_root_is_rejected(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        make_model(outside)
        manager = model_manager.VoiceModelManager()
        with self.assertRaisesRegex(ValueError, "restricted"):
            manager.register_local(str(outside))

    def test_explicit_online_context_restores_offline_state_and_d_cache(self) -> None:
        import os
        from huggingface_hub import constants
        previous_env = os.environ.get("HF_HUB_OFFLINE")
        previous_constant = constants.HF_HUB_OFFLINE
        os.environ["HF_HUB_OFFLINE"] = "1"
        constants.HF_HUB_OFFLINE = True
        try:
            with hf_environment.explicit_huggingface_online():
                self.assertNotIn("HF_HUB_OFFLINE", os.environ)
                self.assertFalse(constants.HF_HUB_OFFLINE)
                self.assertTrue(os.environ["HF_HOME"].startswith(r"D:\AI\Project_SHION\cache\huggingface"))
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            self.assertTrue(constants.HF_HUB_OFFLINE)
        finally:
            if previous_env is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = previous_env
            constants.HF_HUB_OFFLINE = previous_constant

    def test_download_rejects_invalid_saved_revision_before_network(self) -> None:
        manager = model_manager.VoiceModelManager()
        with self.assertRaisesRegex(model_manager.SavedRevisionUnavailable, "Saved revision"):
            manager.download_huggingface("RinneAi/Rinne_Style-Bert-VITS2", "not-a-commit-sha", "model_assets/Rinne")


if __name__ == "__main__":
    unittest.main()
