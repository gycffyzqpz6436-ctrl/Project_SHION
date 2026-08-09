import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "training" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("chat_local", SCRIPTS / "chat_local.py")
chat_local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chat_local)


class ChatLocalTests(unittest.TestCase):
    def test_parser_accepts_modes_and_generation_overrides(self):
        args = chat_local.build_parser().parse_args([
            "--common", "common.yaml", "--model-config", "model.yaml", "--mode", "minimal",
            "--temperature", "0.5", "--max-new-tokens", "128",
        ])
        self.assertEqual(args.mode, "minimal")
        self.assertEqual(args.temperature, 0.5)
        self.assertEqual(args.max_new_tokens, 128)

    def test_conversation_order_for_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "prompt.md"
            prompt.write_text("# Identity\nSHION\n# Synchronization Workflow\nrest", encoding="utf-8")
            history = [{"role": "user", "content": "u"}, {"role": "assistant", "content": "a"}]
            canonical = chat_local.conversation_messages("canonical", prompt, history)
            minimal = chat_local.conversation_messages("minimal", prompt, history)
            self.assertEqual([item["role"] for item in canonical], ["system", "user", "assistant"])
            self.assertEqual([item["role"] for item in minimal], ["user", "assistant"])

    def test_context_limit_and_token_count(self):
        config = Mock(max_position_embeddings=32768, sliding_window=None, text_config=None)
        tokenizer = Mock(model_max_length=32768)
        tokenizer.apply_chat_template.return_value = [1, 2, 3]
        self.assertEqual(chat_local.model_context_limit(config, tokenizer), 32768)
        self.assertEqual(chat_local.rendered_token_count(tokenizer, [{"role": "user", "content": "x"}]), 3)

    def test_adapter_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = Path(directory)
            (adapter / "adapter_config.json").write_text(json.dumps({
                "peft_type": "LORA", "base_model_name_or_path": chat_local.APPROVED_MODEL_ID
            }), encoding="utf-8")
            self.assertEqual(chat_local.validate_adapter(adapter)["peft_type"], "LORA")
            (adapter / "adapter_config.json").write_text(json.dumps({
                "peft_type": "LORA", "base_model_name_or_path": "D:/AI/model-a"
            }), encoding="utf-8")
            self.assertEqual(chat_local.validate_adapter(adapter, Path("D:/AI/model-a"))["peft_type"], "LORA")
            with self.assertRaisesRegex(ValueError, "unexpected base"):
                chat_local.validate_adapter(adapter, Path("D:/AI/different-model"))
            (adapter / "adapter_config.json").write_text('{"peft_type":"IA3"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "LoRA"):
                chat_local.validate_adapter(adapter)

    def test_session_log_is_opt_in_and_preserves_roles(self):
        writer = chat_local.SessionWriter(None, {"mode": "minimal"})
        writer.message({"role": "user", "content": "秘密ではない会話"})
        writer.close()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            writer = chat_local.SessionWriter(path, {"mode": "minimal"})
            writer.message({"role": "user", "content": "こんにちは"})
            writer.message({"role": "assistant", "content": "やあ"})
            writer.close()
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row.get("role") for row in rows[1:]], ["user", "assistant"])
            self.assertNotIn("system_prompt", rows[0])
            with self.assertRaises(FileExistsError):
                chat_local.SessionWriter(path, {})


if __name__ == "__main__":
    unittest.main()
