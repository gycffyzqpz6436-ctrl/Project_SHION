import json
import unittest
from pathlib import Path
from threading import Lock
from unittest.mock import Mock

import torch

from app.runtime.model_runtime import (
    LocalModelRuntime,
    RepeatedSequenceStoppingCriteria,
    effective_generation_limit,
    generation_eos_token_ids,
)


ROOT = Path(__file__).resolve().parents[1]


class RepetitionGuardTests(unittest.TestCase):
    def test_model_specific_eos_tokens_are_preserved(self):
        generation = type("Generation", (), {"eos_token_id": [1, 106, 50]})()
        model = type("Model", (), {"generation_config": generation})()
        tokenizer = type("Tokenizer", (), {"eos_token_id": 1})()
        self.assertEqual(generation_eos_token_ids(model, tokenizer), [1, 106, 50])

    def test_neutral_prompt_is_owner_approved_text(self):
        expected = """You are a natural conversation partner.
Do not behave like a customer-support assistant.
Do not introduce yourself as an AI unless directly asked.
For short casual messages, respond briefly and naturally.
When the user explicitly requests detail or a long response, provide the requested appropriate level of detail and length.
Do not turn casual conversation into advice, explanations, checklists, or recommendations unless requested.
Do not invent relationships, roles, sexual scenarios, or fictional context that the user did not provide.
React naturally to jokes, ambiguity, emotions, and casual remarks.
Stay conversational rather than instructional."""
        actual = (ROOT / "app" / "prompts" / "neutral_conversation.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(actual, expected)

    def test_generation_limit_uses_hard_ceiling_and_remaining_context(self):
        self.assertEqual(effective_generation_limit(100, 4096, 262144), 4096)
        self.assertEqual(effective_generation_limit(260000, 4096, 262144), 2144)
        with self.assertRaises(OverflowError):
            effective_generation_limit(262144, 4096, 262144)

    def test_generate_allows_early_eos_and_passes_clamped_limit(self):
        class Batch(dict):
            def to(self, _device):
                return self

        captured = {}

        def apply_chat_template(_messages, return_tensors=None, **_kwargs):
            if return_tensors is None:
                return list(range(20))
            return Batch(input_ids=torch.arange(20).reshape(1, 20))

        def generate(**kwargs):
            captured.update(kwargs)
            return torch.cat((kwargs["input_ids"], torch.tensor([[99]])), dim=1)

        runtime = LocalModelRuntime.__new__(LocalModelRuntime)
        runtime.neutral_prompt = "neutral"
        runtime.prompt_path = ROOT / "docs" / "unused.md"
        runtime.chat_template_options = {"enable_thinking": False}
        runtime.tokenizer = Mock(
            apply_chat_template=apply_chat_template, decode=Mock(return_value="short reply"),
            eos_token_id=1, pad_token_id=0,
        )
        runtime.model = Mock(
            device=torch.device("cpu"), generate=generate,
            generation_config=Mock(eos_token_id=[1, 106, 50]),
        )
        runtime.generation = {
            "seed": 42, "temperature": 0.7, "top_p": 0.8, "top_k": 20,
            "repetition_penalty": 1.1, "max_new_tokens": 4096,
        }
        runtime.context_limit = 100
        runtime.repetition_guard = None
        runtime.lock = Lock()
        runtime.turns = {}

        response, input_tokens = runtime.generate("session", "minimal", [], "hello")
        self.assertEqual(response, "short reply")
        self.assertEqual(input_tokens, 20)
        self.assertEqual(captured["max_new_tokens"], 80)
        self.assertEqual(captured["eos_token_id"], [1, 106, 50])
        self.assertEqual(captured["input_ids"].shape[1] + captured["max_new_tokens"], 100)

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
        self.assertTrue(registry["gemma4_12b_it_manual"]["available"])
        self.assertNotIn("unavailable_reason", registry["gemma4_12b_it_manual"])
        self.assertEqual(registry["gemma4_12b_it_manual"]["chat_template_options"], {"enable_thinking": False})
        self.assertEqual(registry["gemma4_12b_it_manual"]["generation_overrides"]["max_new_tokens"], 4096)
        self.assertEqual(registry["gemma4_12b_it_manual"]["model_class"], "AutoModelForMultimodalLM")
        self.assertEqual(
            registry["gemma4_12b_it_manual"]["revision"],
            "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        )
        low_refusal = registry["gemma4_12b_heretic_ja_v2_manual"]
        self.assertTrue(low_refusal["available"])
        self.assertEqual(low_refusal["model_class"], "AutoModelForMultimodalLM")
        self.assertEqual(low_refusal["revision"], "90825e3e221c400cda1afdd425b77e0a0241f7f9")
        self.assertEqual(low_refusal["chat_template_options"], {"enable_thinking": False})
        self.assertEqual(low_refusal["generation_overrides"]["max_new_tokens"], 4096)
        self.assertIn("quality not approved", low_refusal["modification_type"])
        self.assertNotIn("generation_overrides", registry["ministral3_official"])
        self.assertNotIn("generation_overrides", registry["nemo12b_official"])


if __name__ == "__main__":
    unittest.main()
