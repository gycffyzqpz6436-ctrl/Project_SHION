"""Single-load, text-only local model runtime shared with chat CLI helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Lock

import torch
import yaml
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoModelForImageTextToText,
    AutoModelForMultimodalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    StoppingCriteria,
    StoppingCriteriaList,
    set_seed,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "training" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chat_local import (  # noqa: E402
    conversation_messages,
    model_context_limit,
    normalize_free_chat_generation_config,
    validate_adapter,
    validate_generation,
)

NEUTRAL_PROMPT_PATH = ROOT / "app" / "prompts" / "neutral_conversation.txt"


def generation_eos_token_ids(model, tokenizer):
    """Preserve model-specific turn/channel terminators when they are declared."""
    configured = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
    return configured if configured is not None else tokenizer.eos_token_id


def effective_generation_limit(input_tokens: int, hard_ceiling: int, context_limit: int) -> int:
    """Clamp generation to remaining context without truncating conversation history."""
    remaining = context_limit - input_tokens
    if remaining <= 0:
        raise OverflowError("conversation has reached the model context limit; start a new chat")
    return min(hard_ceiling, remaining)


class RepeatedSequenceStoppingCriteria(StoppingCriteria):
    """Stop only sustained, consecutive token-block loops in newly generated text."""

    def __init__(self, prompt_length: int, min_block_tokens: int = 4, max_block_tokens: int = 32, repeats: int = 3):
        self.prompt_length = prompt_length
        self.min_block_tokens = min_block_tokens
        self.max_block_tokens = max_block_tokens
        self.repeats = repeats
        self.triggered = False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        generated = input_ids[0, self.prompt_length :].tolist()
        largest = min(self.max_block_tokens, len(generated) // self.repeats)
        for size in range(self.min_block_tokens, largest + 1):
            tail = generated[-size:]
            if all(generated[-size * repeat : -size * (repeat - 1) or None] == tail for repeat in range(2, self.repeats + 1)):
                self.triggered = True
                return True
        return False


class LocalModelRuntime:
    def __init__(self, common_path: Path, alias: str, model_spec: dict, adapter: Path | None = None):
        self.common = yaml.safe_load(common_path.read_text(encoding="utf-8"))
        self.alias = alias
        self.model_spec = dict(model_spec)
        if not self.model_spec.get("available"):
            raise ValueError("model is not approved for local loading")
        if self.model_spec.get("model_class") not in {
            "AutoModelForImageTextToText", "AutoModelForMultimodalLM", "AutoModelForCausalLM"
        }:
            raise ValueError("model class is not allowlisted")
        self.model_path = Path(self.model_spec["local_path"])
        if not self.model_path.is_dir():
            raise ValueError(f"local model directory does not exist: {self.model_path}")
        if adapter is not None and not self.model_spec.get("adapter_allowed"):
            raise ValueError("adapter is not approved for this model")
        validate_adapter(adapter, self.model_path)
        self.adapter = adapter
        self.prompt_path = Path(self.common["canonical_system_prompt"])
        self.neutral_prompt = NEUTRAL_PROMPT_PATH.read_text(encoding="utf-8").strip()
        self.generation = {**self.common["generation"], **self.model_spec.get("generation_overrides", {})}
        validate_generation(self.generation)
        self.repetition_guard = self.model_spec.get("repetition_guard")
        self.chat_template_options = dict(self.model_spec.get("chat_template_options", {}))
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
        loaders = {
            "AutoModelForImageTextToText": AutoModelForImageTextToText,
            "AutoModelForMultimodalLM": AutoModelForMultimodalLM,
            "AutoModelForCausalLM": AutoModelForCausalLM,
        }
        loader = loaders[self.model_spec["model_class"]]
        self.model = loader.from_pretrained(
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
            "model_alias": self.alias,
            "display_name": self.model_spec["display_name"],
            "repo_id": self.model_spec["repo_id"],
            "revision": self.model_spec["revision"],
            "parent_model": self.model_spec["parent_model"],
            "base_origin": self.model_spec.get("base_origin", "not specified"),
            "provenance": self.model_spec["provenance"],
            "modification_type": self.model_spec["modification_type"],
            "parameter_scale": self.model_spec["parameter_scale"],
            "quantization": "4-bit NF4 / BF16 compute",
            "local_model": True,
            "adapter": "none" if self.adapter is None else "LoRA",
            "context_limit": self.context_limit,
            "generation": self.generation,
            "gpu_memory_allocated_mib": round(allocated),
            "gpu_memory_reserved_mib": round(reserved),
        }

    def generate(self, session_id: str, mode: str, history: list[dict], user_text: str) -> tuple[str, int]:
        if mode not in {"minimal", "neutral", "canonical"}:
            raise ValueError("mode must be minimal, neutral, or canonical")
        proposed = history + [{"role": "user", "content": user_text}]
        messages = ([{"role": "system", "content": self.neutral_prompt}, *proposed]
                    if mode == "neutral" else conversation_messages(mode, self.prompt_path, proposed))
        rendered_ids = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, **self.chat_template_options
        )
        input_tokens = len(rendered_ids)
        effective_max_new_tokens = effective_generation_limit(
            input_tokens, self.generation["max_new_tokens"], self.context_limit
        )
        key = (session_id, mode)
        with self.lock:
            batch = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True,
                **self.chat_template_options,
            ).to(self.model.device)
            stopping_criteria = None
            if self.repetition_guard:
                guard = RepeatedSequenceStoppingCriteria(batch["input_ids"].shape[1], **self.repetition_guard)
                stopping_criteria = StoppingCriteriaList([guard])
            set_seed(self.generation["seed"] + self.turns.get(key, 0))
            with torch.inference_mode():
                output_ids = self.model.generate(
                    **batch,
                    do_sample=True,
                    temperature=self.generation["temperature"],
                    top_p=self.generation["top_p"],
                    top_k=self.generation["top_k"],
                    repetition_penalty=self.generation["repetition_penalty"],
                    max_new_tokens=effective_max_new_tokens,
                    eos_token_id=generation_eos_token_ids(self.model, self.tokenizer),
                    pad_token_id=self.tokenizer.pad_token_id,
                    use_cache=True,
                    stopping_criteria=stopping_criteria,
                )
            self.turns[key] = self.turns.get(key, 0) + 1
        response = self.tokenizer.decode(
            output_ids[0, batch["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        return response, input_tokens

    def reset(self, session_id: str) -> None:
        self.turns.pop((session_id, "minimal"), None)
        self.turns.pop((session_id, "neutral"), None)
        self.turns.pop((session_id, "canonical"), None)

    def close(self) -> None:
        import gc

        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
