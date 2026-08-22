import json
import unittest
from pathlib import Path
from threading import Lock
from threading import Event
from unittest.mock import Mock
from unittest.mock import patch

import torch

from app.runtime.model_runtime import (
    LocalModelRuntime,
    CancellationStoppingCriteria,
    RepeatedSequenceStoppingCriteria,
    effective_generation_limit,
    extract_visible_response,
    generation_eos_token_ids,
)
from app.runtime.generation_policy import AdaptiveOutputBudget, RecentTurnContextStrategy, SelfCorrectionPolicy
from app.runtime.fixed_adapter import resolve_fixed_adapter, validate_loaded_adapter
from app.models.registry import ModelRegistry


ROOT = Path(__file__).resolve().parents[1]


class RepetitionGuardTests(unittest.TestCase):
    def test_shion_exp0002_is_bound_to_the_fixed_server_side_adapter(self):
        registry = json.loads((ROOT / "app" / "model_registry.json").read_text(encoding="utf-8"))
        spec = registry["shion_gemma4_exp0002_manual"]
        fixed = spec["fixed_adapter"]
        self.assertFalse(spec["adapter_allowed"])
        self.assertEqual(spec["revision"], "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7")
        self.assertEqual(fixed["expected_target_count"], 184)
        self.assertEqual((fixed["record_count"], fixed["epochs"]), (200, 3))
        self.assertEqual((fixed["rank"], fixed["alpha"], fixed["dropout"]), (8, 16, 0.1))
        self.assertEqual(spec["recommended_mode"], "neutral")
        self.assertEqual(spec["generation_overrides"], registry["gemma4_12b_it_manual"]["generation_overrides"])
        self.assertEqual(spec["chat_template_options"], {"enable_thinking": False})

    def test_fixed_adapter_rejects_any_client_override_before_loading(self):
        spec = {"fixed_adapter": {"local_path": "server-owned"}}
        with self.assertRaisesRegex(ValueError, "overrides are prohibited"):
            resolve_fixed_adapter(spec, Path("client-supplied"), Path("base"))

    def test_public_model_metadata_does_not_disclose_fixed_adapter_path(self):
        registry = ModelRegistry.from_file(ROOT / "app" / "model_registry.json")
        public = next(item for item in registry.public_models()
                      if item["alias"] == "shion_gemma4_exp0002_manual")
        self.assertNotIn("fixed_adapter", public)
        self.assertNotIn("local_path", public)

    def test_loaded_adapter_must_be_active_with_exact_target_count(self):
        binding = Mock(expected_target_count=2)
        model = Mock(peft_config={"default": object()}, active_adapter="default")
        model.named_modules.return_value = [
            ("model.layers.0.self_attn.q_proj.lora_A.default", object()),
            ("model.layers.0.self_attn.k_proj.lora_A.default", object()),
        ]
        validate_loaded_adapter(model, binding)
        model.named_modules.return_value = model.named_modules.return_value[:1]
        with self.assertRaisesRegex(ValueError, "expected 2"):
            validate_loaded_adapter(model, binding)

    def test_self_correction_detects_owner_doubt_without_arithmetic_rules(self):
        policy = SelfCorrectionPolicy()
        for message in ("違う", "？", "本当？", "それ間違ってない？", "200", "再確認してください"):
            self.assertTrue(policy.is_review_request(message), message)
        for message in ("こんにちは", "1+199は？", "詳しく説明して"):
            self.assertFalse(policy.is_review_request(message), message)

    def test_self_correction_withholds_challenged_assistant_claims_by_provenance(self):
        policy = SelfCorrectionPolicy()
        history = [
            {"role": "user", "content": "今夜更かし中"},
            {"role": "assistant", "content": "何をしていますか？"},
            {"role": "user", "content": "１＋１９９＝"},
            {"role": "assistant", "content": "201です"},
            {"role": "user", "content": "？"},
            {"role": "assistant", "content": "201です"},
        ]
        review = policy.review(history, "200")
        self.assertTrue(review.active)
        self.assertEqual(review.assistant_messages_withheld, 2)
        self.assertEqual([item["content"] for item in review.history],
                         ["今夜更かし中", "何をしていますか？", "1+199=", "?"])
        self.assertNotIn("201です", [item["content"] for item in review.history])

    def test_numeric_answer_to_assistant_question_is_not_misclassified(self):
        policy = SelfCorrectionPolicy()
        history = [{"role": "user", "content": "年齢を聞いて"},
                   {"role": "assistant", "content": "何歳ですか？"}]
        self.assertFalse(policy.review(history, "30").active)

    def test_gemma_visible_channel_excludes_thought_and_draft(self):
        tokenizer = Mock(all_special_tokens=["<eos>"])
        tokenizer.decode.side_effect = lambda _ids, skip_special_tokens=False: (
            "<|channel>thought\nprivate draft<channel|>\n"
            "<|channel>final\n表示する回答です。<channel|><eos>"
            if not skip_special_tokens else "private draft 表示する回答です。"
        )
        visible, filtered = extract_visible_response(tokenizer, [1, 2, 3])
        self.assertEqual(visible, "表示する回答です。")
        self.assertTrue(filtered)

    def test_thought_only_generation_returns_no_private_text(self):
        tokenizer = Mock(all_special_tokens=[])
        tokenizer.decode.side_effect = lambda _ids, skip_special_tokens=False: (
            "<|channel>thought\nprivate draft without final" if not skip_special_tokens else "private draft without final"
        )
        visible, filtered = extract_visible_response(tokenizer, [1, 2, 3])
        self.assertEqual(visible, "")
        self.assertTrue(filtered)

    def test_fixed_seed_reproduction_can_recover_after_owner_challenge(self):
        class Batch(dict):
            def to(self, _device):
                return self

        rendered_messages = []

        def apply_chat_template(messages, return_tensors=None, return_dict=False, **_kwargs):
            rendered_messages[:] = messages
            if return_tensors is None:
                return {"input_ids": list(range(24))} if return_dict else list(range(24))
            return Batch(input_ids=torch.arange(24).reshape(1, 24))

        def generate(**kwargs):
            reviewing = any(SelfCorrectionPolicy.REVIEW_INSTRUCTION in item.get("content", "")
                            for item in rendered_messages)
            answer = 200 if reviewing else 201
            return torch.cat((kwargs["input_ids"], torch.tensor([[answer]])), dim=1)

        tokenizer = Mock(
            apply_chat_template=apply_chat_template,
            encode=Mock(return_value=[1]),
            eos_token_id=1,
            pad_token_id=0,
            all_special_tokens=[],
        )
        tokenizer.decode.side_effect = lambda ids, skip_special_tokens=False: str(int(ids[0]))
        runtime = LocalModelRuntime.__new__(LocalModelRuntime)
        runtime.neutral_prompt = "neutral"
        runtime.prompt_path = ROOT / "docs" / "unused.md"
        runtime.chat_template_options = {"enable_thinking": False}
        runtime.tokenizer = tokenizer
        runtime.model = Mock(device=torch.device("cpu"), generate=generate,
                             generation_config=Mock(eos_token_id=1))
        runtime.generation = {"seed": 3407, "temperature": .7, "top_p": .8, "top_k": 20,
                              "repetition_penalty": 1.1, "max_new_tokens": 512}
        runtime.context_limit = 1024
        runtime.repetition_guard = None
        runtime.context_strategy = RecentTurnContextStrategy()
        runtime.output_budget = AdaptiveOutputBudget()
        runtime.self_correction = SelfCorrectionPolicy()
        runtime.input_budget = 6144
        runtime.lock = Lock()
        runtime.turns = {("fixture", "neutral"): 1}
        history = [{"role": "user", "content": "今夜更かし中"},
                   {"role": "assistant", "content": "まだ起きているんですね。"}]

        seeds = []
        with patch("app.runtime.model_runtime.set_seed", side_effect=seeds.append):
            first, _ = runtime.generate("fixture", "neutral", history, "１＋１９９＝")
            history.extend(({"role": "user", "content": "１＋１９９＝"},
                            {"role": "assistant", "content": first}))
            corrected, telemetry = runtime.generate("fixture", "neutral", history, "？")

        self.assertEqual(first, "201")  # Captures the observed sampling failure as a fixture.
        self.assertEqual(corrected, "200")
        self.assertEqual(seeds, [3408, 3409])
        self.assertTrue(telemetry["self_correction_review"])
        self.assertEqual(telemetry["assistant_history_withheld"], 1)
        self.assertEqual(telemetry["decoding_mode"], "verification_greedy")
        rendered_content = [item.get("content") for item in rendered_messages]
        self.assertNotIn("201", rendered_content)
        self.assertIn("1+199=", rendered_content)

    def test_cancellation_stopping_criteria_is_owner_controlled(self):
        event = Event()
        guard = CancellationStoppingCriteria(event)
        self.assertFalse(guard(torch.tensor([[1]]), torch.empty(0)))
        event.set()
        self.assertTrue(guard(torch.tensor([[1, 2]]), torch.empty(0)))

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

        def apply_chat_template(_messages, return_tensors=None, return_dict=False, **_kwargs):
            if return_tensors is None:
                return {"input_ids": list(range(20)), "attention_mask": [1] * 20} if return_dict else list(range(20))
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
            encode=Mock(return_value=[1]),
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
        runtime.context_strategy = RecentTurnContextStrategy()
        runtime.output_budget = AdaptiveOutputBudget()
        runtime.input_budget = 80
        runtime.lock = Lock()
        runtime.turns = {}

        response, telemetry = runtime.generate("session", "minimal", [], "hello")
        self.assertEqual(response, "short reply")
        self.assertEqual(telemetry["total_input_tokens"], 20)
        self.assertEqual(telemetry["output_tokens"], 1)
        self.assertEqual(captured["max_new_tokens"], 80)
        self.assertEqual(captured["eos_token_id"], [1, 106, 50])
        self.assertEqual(captured["input_ids"].shape[1] + captured["max_new_tokens"], 100)

    def test_token_count_uses_input_id_sequence_not_mapping_length(self):
        runtime = LocalModelRuntime.__new__(LocalModelRuntime)
        runtime.chat_template_options = {"enable_thinking": False}
        runtime.tokenizer = Mock(apply_chat_template=Mock(return_value={"input_ids": list(range(321)), "attention_mask": [1] * 321}))
        self.assertEqual(runtime._token_count([{"role":"user","content":"hello"}]), 321)

    def test_recent_turn_budget_keeps_current_message_and_omits_oldest_turns(self):
        strategy = RecentTurnContextStrategy()
        history = [{"role":"user","content":"old"},{"role":"assistant","content":"old reply"},
                   {"role":"user","content":"recent"},{"role":"assistant","content":"recent reply"}]
        mandatory = [{"role":"system","content":"system"},{"role":"user","content":"current"}]
        count = lambda messages: sum(len(item["content"].split()) + 1 for item in messages)
        selection = strategy.select(history, mandatory, count, budget=9)
        self.assertEqual([item["content"] for item in selection.messages], ["system","recent","recent reply","current"])
        self.assertGreater(selection.history_tokens_omitted, 0)
        self.assertEqual(selection.history_messages_omitted, 2)

    def test_adaptive_output_budget_is_bounded_by_explicit_intent(self):
        policy = AdaptiveOutputBudget()
        self.assertEqual(vars(policy.resolve("一文で答えて", 4096)), {"intent":"short","max_new_tokens":128})
        self.assertEqual(vars(policy.resolve("今日どうだった？", 4096)), {"intent":"normal","max_new_tokens":512})
        self.assertEqual(vars(policy.resolve("詳しく長文で説明して", 4096)), {"intent":"long","max_new_tokens":2048})
        self.assertEqual(vars(policy.resolve("できるだけ長く4096 tokensで", 4096)), {"intent":"maximum","max_new_tokens":4096})

    def test_stops_three_consecutive_repeated_blocks(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 10, 11, 12, 13, 10, 11, 12, 13]])
        self.assertTrue(guard(ids, torch.empty(0)))
        self.assertTrue(guard.triggered)

    def test_does_not_stop_ordinary_nonconsecutive_repetition(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=2, min_block_tokens=4, max_block_tokens=8, repeats=3)
        ids = torch.tensor([[1, 2, 10, 11, 12, 13, 20, 10, 11, 12, 13]])
        self.assertFalse(guard(ids, torch.empty(0)))

    def test_conservative_guard_waits_for_minimum_output(self):
        guard = RepeatedSequenceStoppingCriteria(prompt_length=1, min_block_tokens=4, max_block_tokens=8,
                                                 repeats=4, min_generated_tokens=20)
        repeated = torch.tensor([[1] + [10,11,12,13] * 4])
        self.assertFalse(guard(repeated, torch.empty(0)))
        repeated = torch.tensor([[1] + [20,21,22,23] + [10,11,12,13] * 4])
        self.assertTrue(guard(repeated, torch.empty(0)))

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
        self.assertEqual(low_refusal["input_context_budget"], 6144)
        self.assertEqual(low_refusal["repetition_guard"]["repeats"], 4)
        self.assertIn("quality not approved", low_refusal["modification_type"])
        self.assertNotIn("generation_overrides", registry["ministral3_official"])
        self.assertNotIn("generation_overrides", registry["nemo12b_official"])


if __name__ == "__main__":
    unittest.main()
