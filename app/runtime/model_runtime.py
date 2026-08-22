"""Single-load, text-only local model runtime shared with chat CLI helpers."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from threading import Event, Lock

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
from app.runtime.generation_policy import AdaptiveOutputBudget, RecentTurnContextStrategy, SelfCorrectionPolicy
from app.runtime.fixed_adapter import resolve_fixed_adapter, validate_loaded_adapter

NEUTRAL_PROMPT_PATH = ROOT / "app" / "prompts" / "neutral_conversation.txt"
SAFE_RESPONSE_FALLBACK = "応答を安全に表示できませんでした。もう一度お試しください。"


def extract_visible_response(tokenizer, generated_ids) -> tuple[str, bool]:
    """Decode only the visible Assistant channel, never a model's private draft channel."""
    raw = tokenizer.decode(generated_ids, skip_special_tokens=False).strip()
    channel = re.compile(r"<\|channel\>(thought|analysis|final)\s*(.*?)(?:<channel\|>|$)", re.I | re.S)
    matches = list(channel.finditer(raw))
    private_seen = any(match.group(1).casefold() in {"thought", "analysis"} for match in matches)
    finals = [match.group(2).strip() for match in matches if match.group(1).casefold() == "final"]
    if finals:
        return finals[-1], private_seen
    if private_seen:
        visible = channel.sub(lambda match: "" if match.group(1).casefold() in {"thought", "analysis"}
                              else match.group(2), raw).strip()
        for token in getattr(tokenizer, "all_special_tokens", []):
            visible = visible.replace(token, "")
        return visible.strip(), True
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip(), False


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

    def __init__(self, prompt_length: int, min_block_tokens: int = 4, max_block_tokens: int = 32,
                 repeats: int = 3, min_generated_tokens: int = 0):
        self.prompt_length = prompt_length
        self.min_block_tokens = min_block_tokens
        self.max_block_tokens = max_block_tokens
        self.repeats = repeats
        self.min_generated_tokens = min_generated_tokens
        self.triggered = False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        generated = input_ids[0, self.prompt_length :].tolist()
        if len(generated) < self.min_generated_tokens:
            return False
        largest = min(self.max_block_tokens, len(generated) // self.repeats)
        for size in range(self.min_block_tokens, largest + 1):
            tail = generated[-size:]
            if all(generated[-size * repeat : -size * (repeat - 1) or None] == tail for repeat in range(2, self.repeats + 1)):
                self.triggered = True
                return True
        return False


class CancellationStoppingCriteria(StoppingCriteria):
    """Stop generation when the Owner requests cancellation for this session."""

    def __init__(self, event: Event):
        self.event = event

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        return self.event.is_set()


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
        self.fixed_adapter = resolve_fixed_adapter(self.model_spec, adapter, self.model_path)
        if adapter is not None and not self.model_spec.get("adapter_allowed"):
            raise ValueError("adapter is not approved for this model")
        self.adapter = self.fixed_adapter.path if self.fixed_adapter else adapter
        validate_adapter(self.adapter, self.model_path)
        self.prompt_path = Path(self.common["canonical_system_prompt"])
        self.neutral_prompt = NEUTRAL_PROMPT_PATH.read_text(encoding="utf-8").strip()
        self.generation = {**self.common["generation"], **self.model_spec.get("generation_overrides", {})}
        validate_generation(self.generation)
        self.repetition_guard = self.model_spec.get("repetition_guard")
        self.chat_template_options = dict(self.model_spec.get("chat_template_options", {}))
        self.lock = Lock()
        self.turns: dict[tuple[str, str], int] = {}
        self.cancel_events: dict[str, Event] = {}
        self.context_strategy = RecentTurnContextStrategy()
        self.output_budget = AdaptiveOutputBudget()
        self.self_correction = SelfCorrectionPolicy()
        self.input_budget = int(self.model_spec.get("input_context_budget", 8192))

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
        if self.adapter is not None:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(
                self.model, self.adapter, is_trainable=False, local_files_only=True
            )
            if self.fixed_adapter:
                validate_loaded_adapter(self.model, self.fixed_adapter)
        normalize_free_chat_generation_config(self.model)
        self.model.eval()

    def status(self) -> dict:
        allocated = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
        reserved = torch.cuda.memory_reserved() / 1024**2 if torch.cuda.is_available() else 0
        result = {
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
        if self.fixed_adapter:
            result.update({
                "model_identity": "SHION",
                "base_model_label": "Gemma 4 12B IT",
                "experiment": "0002",
                "adapter": "active",
                "adapter_status": "ACTIVE",
                "adapter_target_count": self.fixed_adapter.expected_target_count,
                "dataset_label": self.fixed_adapter.dataset,
                "training_epochs": self.fixed_adapter.epochs,
                "lora_config": (f"r={self.fixed_adapter.rank} / alpha={self.fixed_adapter.alpha} / "
                                f"dropout={self.fixed_adapter.dropout:g}"),
                "evaluation_status": self.fixed_adapter.status,
                "recommended_mode": self.model_spec.get("recommended_mode", "neutral"),
            })
        return result

    def _token_count(self, messages: list[dict]) -> int:
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True,
            **self.chat_template_options,
        )
        input_ids = rendered["input_ids"]
        return len(input_ids[0]) if input_ids and isinstance(input_ids[0], list) else len(input_ids)

    def generate(self, session_id: str, mode: str, history: list[dict], user_text: str,
                 memory_context: str = "") -> tuple[str, dict]:
        if mode not in {"minimal", "neutral", "canonical"}:
            raise ValueError("mode must be minimal, neutral, or canonical")
        cancel_event = Event()
        if not hasattr(self, "cancel_events"):
            self.cancel_events = {}
        self.cancel_events[session_id] = cancel_event
        system_messages = ([{"role": "system", "content": self.neutral_prompt}] if mode == "neutral"
                           else conversation_messages(mode, self.prompt_path, []) )
        system_tokens = sum(len(self.tokenizer.encode(item["content"], add_special_tokens=False))
                            for item in system_messages)
        if memory_context:
            if system_messages and system_messages[0].get("role") == "system":
                system_messages[0] = {**system_messages[0], "content": f"{system_messages[0]['content']}\n\n{memory_context}"}
            else:
                system_messages.insert(0, {"role": "system", "content": memory_context})
        correction_policy = getattr(self, "self_correction", SelfCorrectionPolicy())
        correction = correction_policy.review(history, user_text)
        if correction.active:
            if system_messages and system_messages[0].get("role") == "system":
                system_messages[0] = {
                    **system_messages[0],
                    "content": f"{system_messages[0]['content']}\n\n{correction_policy.REVIEW_INSTRUCTION}",
                }
            else:
                system_messages.insert(0, {"role": "system", "content": correction_policy.REVIEW_INSTRUCTION})
        mandatory = [*system_messages, {"role": "user", "content": user_text}]
        prompt_started = time.perf_counter()
        selection = self.context_strategy.select(correction.history, mandatory, self._token_count, self.input_budget)
        messages = selection.messages
        input_tokens = selection.total_input_tokens
        selection_build_ms = (time.perf_counter() - prompt_started) * 1000
        requested_output = self.output_budget.resolve(user_text, self.generation["max_new_tokens"])
        effective_max_new_tokens = effective_generation_limit(
            input_tokens, requested_output.max_new_tokens, self.context_limit
        )
        key = (session_id, mode)
        with self.lock:
            batch_started = time.perf_counter()
            batch = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True,
                **self.chat_template_options,
            ).to(self.model.device)
            prompt_build_ms = round(selection_build_ms + (time.perf_counter() - batch_started) * 1000, 3)
            criteria = [CancellationStoppingCriteria(cancel_event)]
            if self.repetition_guard:
                guard = RepeatedSequenceStoppingCriteria(batch["input_ids"].shape[1], **self.repetition_guard)
                criteria.append(guard)
            set_seed(self.generation["seed"] + self.turns.get(key, 0))
            generation_started = time.perf_counter()
            decoding = ({"do_sample": False} if correction.active else {
                "do_sample": True,
                "temperature": self.generation["temperature"],
                "top_p": self.generation["top_p"],
                "top_k": self.generation["top_k"],
            })
            with torch.inference_mode():
                output_ids = self.model.generate(
                    **batch,
                    **decoding,
                    repetition_penalty=self.generation["repetition_penalty"],
                    max_new_tokens=effective_max_new_tokens,
                    eos_token_id=generation_eos_token_ids(self.model, self.tokenizer),
                    pad_token_id=self.tokenizer.pad_token_id,
                    use_cache=True,
                    stopping_criteria=StoppingCriteriaList(criteria),
                )
            self.turns[key] = self.turns.get(key, 0) + 1
            generation_ms = round((time.perf_counter() - generation_started) * 1000)
        self.cancel_events.pop(session_id, None)
        generated_ids = output_ids[0, batch["input_ids"].shape[1]:]
        response, private_channel_filtered = extract_visible_response(self.tokenizer, generated_ids)
        if not response and private_channel_filtered:
            response = SAFE_RESPONSE_FALLBACK
        output_tokens = int(generated_ids.shape[0])
        eos_ids = generation_eos_token_ids(self.model, self.tokenizer)
        eos_ids = {int(eos_ids)} if isinstance(eos_ids, int) else {int(item) for item in eos_ids}
        if cancel_event.is_set(): stop_reason = "owner_stop"
        elif self.repetition_guard and guard.triggered: stop_reason = "repetition_guard"
        elif output_tokens and int(generated_ids[-1]) in eos_ids: stop_reason = "eos"
        elif output_tokens >= effective_max_new_tokens: stop_reason = "max_tokens"
        else: stop_reason = "generation_complete"
        current_tokens = len(self.tokenizer.encode(user_text, add_special_tokens=False))
        memory_tokens = len(self.tokenizer.encode(memory_context, add_special_tokens=False)) if memory_context else 0
        telemetry = {
            "context_tokens": input_tokens,
            "total_input_tokens": input_tokens,
            "conversation_history_tokens_included": selection.history_tokens_included,
            "conversation_history_tokens_omitted": selection.history_tokens_omitted,
            "conversation_history_messages_included": selection.history_messages_included,
            "conversation_history_messages_omitted": selection.history_messages_omitted,
            "memory_tokens": memory_tokens,
            "system_tokens": system_tokens,
            "character_context_tokens": 0,
            "current_message_tokens": current_tokens,
            "output_tokens": output_tokens,
            "generation_ms": generation_ms,
            "tokens_per_second": round(output_tokens / (generation_ms / 1000), 3) if generation_ms else None,
            "stop_reason": stop_reason,
            "output_intent": requested_output.intent,
            "output_budget_tokens": effective_max_new_tokens,
            "input_budget_tokens": self.input_budget,
            "prompt_build_ms": prompt_build_ms,
            "self_correction_review": correction.active,
            "assistant_history_withheld": correction.assistant_messages_withheld,
            "private_channel_filtered": private_channel_filtered,
            "decoding_mode": "verification_greedy" if correction.active else "conversation_sampling",
        }
        return response, telemetry

    def cancel(self, session_id: str) -> bool:
        event = self.cancel_events.get(session_id)
        if event is None:
            return False
        event.set()
        return True

    def reset(self, session_id: str) -> None:
        self.cancel_events.pop(session_id, None)
        self.turns.pop((session_id, "minimal"), None)
        self.turns.pop((session_id, "neutral"), None)
        self.turns.pop((session_id, "canonical"), None)

    def close(self) -> None:
        import gc

        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
