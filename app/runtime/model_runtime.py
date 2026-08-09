"""Single-load, text-only local model runtime shared with chat CLI helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Lock

import torch
import yaml
from transformers import AutoConfig, AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig, set_seed


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "training" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chat_local import (  # noqa: E402
    APPROVED_MODEL_ID,
    conversation_messages,
    model_context_limit,
    normalize_free_chat_generation_config,
    rendered_token_count,
    validate_adapter,
    validate_generation,
)


class LocalModelRuntime:
    def __init__(self, common_path: Path, model_config_path: Path, adapter: Path | None = None):
        self.common = yaml.safe_load(common_path.read_text(encoding="utf-8"))
        self.model_cfg = yaml.safe_load(model_config_path.read_text(encoding="utf-8"))
        if self.model_cfg.get("model_id") != APPROVED_MODEL_ID:
            raise ValueError("web runtime is locked to the approved Model A")
        if self.model_cfg.get("model_class") != "AutoModelForImageTextToText":
            raise ValueError("unexpected Model A class")
        self.model_path = Path(self.model_cfg["model_path"])
        if not self.model_path.is_dir():
            raise ValueError(f"local model directory does not exist: {self.model_path}")
        validate_adapter(adapter, self.model_path)
        self.adapter = adapter
        self.prompt_path = Path(self.common["canonical_system_prompt"])
        self.generation = dict(self.common["generation"])
        validate_generation(self.generation)
        self.lock = Lock()
        self.turns: dict[tuple[str, str], int] = {}

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
        )
        config = AutoConfig.from_pretrained(self.model_path, local_files_only=True, trust_remote_code=False)
        self.context_limit = model_context_limit(config, self.tokenizer)
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_path,
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            device_map="auto",
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
        )
        if adapter is not None:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, adapter, is_trainable=False)
        normalize_free_chat_generation_config(self.model)
        self.model.eval()

    def status(self) -> dict:
        allocated = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
        reserved = torch.cuda.memory_reserved() / 1024**2 if torch.cuda.is_available() else 0
        return {
            "model": self.model_cfg["model_id"],
            "revision": self.model_cfg["model_revision"],
            "adapter": "none" if self.adapter is None else "LoRA",
            "context_limit": self.context_limit,
            "generation": self.generation,
            "gpu_memory_allocated_mib": round(allocated),
            "gpu_memory_reserved_mib": round(reserved),
        }

    def generate(self, session_id: str, mode: str, history: list[dict], user_text: str) -> tuple[str, int]:
        if mode not in {"minimal", "canonical"}:
            raise ValueError("mode must be minimal or canonical")
        proposed = history + [{"role": "user", "content": user_text}]
        messages = conversation_messages(mode, self.prompt_path, proposed)
        input_tokens = rendered_token_count(self.tokenizer, messages, add_generation_prompt=True)
        projected = input_tokens + self.generation["max_new_tokens"]
        if projected > self.context_limit:
            raise OverflowError("会話がコンテキスト上限に達しました。新しいチャットを開始してください。")
        key = (session_id, mode)
        with self.lock:
            batch = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True
            ).to(self.model.device)
            set_seed(self.generation["seed"] + self.turns.get(key, 0))
            with torch.inference_mode():
                output_ids = self.model.generate(
                    **batch,
                    do_sample=True,
                    temperature=self.generation["temperature"],
                    top_p=self.generation["top_p"],
                    top_k=self.generation["top_k"],
                    repetition_penalty=self.generation["repetition_penalty"],
                    max_new_tokens=self.generation["max_new_tokens"],
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            self.turns[key] = self.turns.get(key, 0) + 1
        response = self.tokenizer.decode(
            output_ids[0, batch["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        return response, input_tokens

    def reset(self, session_id: str) -> None:
        self.turns.pop((session_id, "minimal"), None)
        self.turns.pop((session_id, "canonical"), None)
