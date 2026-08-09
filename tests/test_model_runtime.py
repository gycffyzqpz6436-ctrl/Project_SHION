import json
import unittest
from pathlib import Path

import torch

from app.runtime.model_runtime import RepeatedSequenceStoppingCriteria


ROOT = Path(__file__).resolve().parents[1]


class RepetitionGuardTests(unittest.TestCase):
    def test_neutral_prompt_is_owner_approved_text(self):
        expected = """You are a natural conversation partner.
Do not behave like a customer-support assistant.
Do not introduce yourself as an AI unless directly asked.
For short casual messages, respond briefly and naturally.
Do not turn casual conversation into advice, explanations, checklists, or recommendations unless requested.
Do not invent relationships, roles, sexual scenarios, or fictional context that the user did not provide.
React naturally to jokes, ambiguity, emotions, and casual remarks.
Stay conversational rather than instructional."""
        actual = (ROOT / "app" / "prompts" / "neutral_conversation.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(actual, expected)

    def test_stops_three_consecutive_repeated_blocks(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 10, 11, 12, 13, 10, 11, 12, 13]])
        self.assertTrue(guard(ids, torch.empty(0)))
        self.assertTrue(guard.triggered)

    def test_does_not_stop_ordinary_nonconsecutive_repetition(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 20, 10, 11, 12, 13]])
        self.assertFalse(guard(ids, torch.empty(0)))

    def test_owner_manual_models_are_allowlisted_with_fixed_settings(self):
        registry = json.loads((ROOT / "app" / "model_registry.json").read_text(encoding="utf-8"))
        self.assertNotIn("impish_nemo12b_experimental", registry)
        self.assertNotIn("shisa_v2_nemo12b_experimental", registry)
        for alias in ("qwen3_8b_erp_manual", "qwen3_8b_jp_uncensored_manual"):
            spec = registry[alias]
            self.assertTrue(spec["available"])
            self.assertIn("Owner Manual Test", spec["provenance"])
            self.assertEqual(spec["generation_overrides"], {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repetition_penalty": 1.1, "max_new_tokens": 128})
            self.assertEqual(spec["chat_template_options"], {"enable_thinking": False})
        self.assertFalse(registry["gemma4_12b_it_manual"]["available"])
        self.assertIn("NF4 GPU load", registry["gemma4_12b_it_manual"]["unavailable_reason"])
        self.assertEqual(registry["gemma4_12b_it_manual"]["chat_template_options"], {"enable_thinking": False})
        self.assertEqual(registry["gemma4_12b_it_manual"]["model_class"], "AutoModelForMultimodalLM")
        self.assertEqual(
            registry["gemma4_12b_it_manual"]["revision"],
            "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        )
        self.assertNotIn("generation_overrides", registry["ministral3_official"])
        self.assertNotIn("generation_overrides", registry["nemo12b_official"])


if __name__ == "__main__":
    unittest.main()
