import tempfile
import unittest
import wave
from pathlib import Path

from app.storage.conversation_db import ConversationRepository
from app.voice.service import VoiceServiceClient, VoiceUnavailable


class FakeVoiceClient(VoiceServiceClient):
    approved = False

    def _start(self):
        return None

    def _request(self, path, payload=None, timeout=10):
        if path == "/api/meta":
            presets = [{"preset_name": "SHION Default", "owner_approved": True,
                        "voice_model": "nene_v3_candidate", "style": "Bright", "style_weight": 1.0,
                        "length": 1.0, "pitch_scale": 1.0, "intonation_scale": 1.0, "sdp_ratio": .2,
                        "noise": .6, "noise_w": .8, "assist_text": "", "assist_text_weight": .7}] if self.approved else []
            return {"presets": presets, "models": {"F1": {"name": "JVNV F1", "styles": ["Neutral"]},
                    "nene_v3_candidate": {"name": "Nene V3", "styles": ["Neutral", "Bright", "Soft"]}},
                    "managed_models": [{"id": "F1", "revision": "fixed-revision"},
                                       {"id": "nene_v3_candidate", "revision": "nene-revision"}]}
        if path == "/api/generate":
            output = self.artifact_root / "voice-tuning" / f"generated-{len(list(self.artifact_root.rglob('*.wav')))}.wav"
            output.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output), "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100); wav.writeframes(b"\0\0" * 441)
            return {"path": str(output), "settings": payload,
                    "metrics": {"wav_duration_seconds": .01, "latency_seconds": .1, "peak_allocated_mib": 10}}
        raise AssertionError(path)


class VoiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.repository = ConversationRepository(self.root / "data" / "chat.db", enabled=True); self.repository.migrate()
        self.repository.create_session({"session_id": "session-0001", "title": "Voice", "created_at": "x", "updated_at": "x", "conversation_mode": "neutral"})
        self.repository.save_message({"message_id": "assistant-0001", "session_id": "session-0001", "role": "assistant", "created_at": "x",
                                      "parts": [{"type": "text", "text": "**こんにちは** https://example.com"}]})
        self.repository.add_response_version("assistant-0001", 1, [{"type": "text", "text": "**こんにちは** https://example.com"}],
                                             {"created_at": "x", "model_id": "model", "model_revision": "rev", "generation": {}})
        self.client = FakeVoiceClient(self.root, Path.cwd(), self.repository)

    def tearDown(self): self.temporary.cleanup()

    def test_read_aloud_retry_and_version_identity(self):
        first = self.client.generate("assistant-0001", 1, None, "F1", "Neutral")
        second = self.client.generate("assistant-0001", 1, None, "F1", "Neutral", retry=True)
        self.assertEqual((first["attempt"], second["attempt"]), (1, 2))
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertEqual(self.client.artifact(first["artifact_id"])[0].suffix, ".wav")
        self.assertEqual(len(self.repository.list_voice_artifacts("assistant-0001", 1)), 2)

    def test_developer_style_is_allowlisted(self):
        with self.assertRaisesRegex(ValueError, "style is unavailable"):
            self.client.generate("assistant-0001", 1, None, "F1", "Unregistered")

    def test_no_approved_preset_and_text_normalization(self):
        with self.assertRaisesRegex(ValueError, "No approved"):
            self.client.generate("assistant-0001", 1, None)
        self.assertEqual(self.client.normalize("**hello** https://example.com"), "hello URL")

    def test_shion_default_resolves_without_manual_selection(self):
        self.client.approved = True
        result = self.client.generate("assistant-0001", 1, None)
        self.assertEqual(result["voice_model_id"], "nene_v3_candidate")
        self.assertEqual(result["voice_style"], "Bright")
        self.assertEqual(result["voice_preset_id"], "SHION Default")
        self.assertEqual(result["voice_revision"], "nene-revision")
        self.assertEqual(result["generation_metadata"]["voice_style"], "Bright")

    def test_failure_does_not_remove_conversation(self):
        self.client._request = lambda *args, **kwargs: (_ for _ in ()).throw(VoiceUnavailable("OOM"))
        with self.assertRaises(VoiceUnavailable): self.client.generate("assistant-0001", 1, None, "F1")
        self.assertEqual(self.repository.load_session("session-0001")["messages"][0]["message_id"], "assistant-0001")


if __name__ == "__main__": unittest.main()
