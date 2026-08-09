"""Interactive, text-only chat with the pinned local Ministral base model."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml
from transformers import AutoConfig, AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig, set_seed

from prompt_utils import system_prompt_for_mode


APPROVED_MODEL_ID = "mistralai/Ministral-3-8B-Instruct-2512-BF16"


def configure_utf8_console() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def load_settings(common_path: Path, model_path: Path, args: argparse.Namespace) -> tuple[dict, dict, dict]:
    common = yaml.safe_load(common_path.read_text(encoding="utf-8"))
    model_cfg = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    if model_cfg.get("model_id") != APPROVED_MODEL_ID:
        raise ValueError("chat_local.py is locked to the approved Model A")
    if model_cfg.get("model_class") != "AutoModelForImageTextToText":
        raise ValueError("unexpected Model A class")
    defaults = common["generation"]
    generation = {
        "temperature": defaults["temperature"] if args.temperature is None else args.temperature,
        "top_p": defaults["top_p"] if args.top_p is None else args.top_p,
        "top_k": defaults["top_k"] if args.top_k is None else args.top_k,
        "repetition_penalty": defaults["repetition_penalty"] if args.repetition_penalty is None else args.repetition_penalty,
        "max_new_tokens": defaults["max_new_tokens"] if args.max_new_tokens is None else args.max_new_tokens,
        "seed": defaults["seed"] if args.seed is None else args.seed,
    }
    validate_generation(generation)
    return common, model_cfg, generation


def validate_generation(settings: dict) -> None:
    if settings["temperature"] <= 0 or not 0 < settings["top_p"] <= 1:
        raise ValueError("temperature must be > 0 and top_p must be in (0, 1]")
    if settings["top_k"] < 0 or settings["repetition_penalty"] <= 0:
        raise ValueError("top_k must be >= 0 and repetition_penalty must be > 0")
    if settings["max_new_tokens"] <= 0 or settings["seed"] < 0:
        raise ValueError("max_new_tokens must be > 0 and seed must be >= 0")


def validate_adapter(path: Path | None, approved_local_model: Path | None = None) -> dict | None:
    if path is None:
        return None
    if not path.is_dir():
        raise ValueError(f"adapter directory does not exist: {path}")
    config_path = path / "adapter_config.json"
    if not config_path.is_file():
        raise ValueError(f"adapter_config.json not found: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if str(config.get("peft_type", "")).upper() != "LORA":
        raise ValueError("only a PEFT LoRA adapter is supported")
    base_name = config.get("base_model_name_or_path")
    if base_name:
        normalized_base = str(base_name).replace("\\", "/").rstrip("/").casefold()
        allowed = {APPROVED_MODEL_ID.casefold()}
        if approved_local_model is not None:
            allowed.add(str(approved_local_model).replace("\\", "/").rstrip("/").casefold())
        if normalized_base not in allowed:
            raise ValueError(f"adapter declares an unexpected base model: {base_name}")
    return config


def model_context_limit(config: Any, tokenizer: Any) -> int:
    candidates: list[int] = []
    for obj in (config, getattr(config, "text_config", None)):
        value = getattr(obj, "max_position_embeddings", None) if obj is not None else None
        if isinstance(value, int) and 0 < value < 10_000_000:
            candidates.append(value)
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < 10_000_000:
        candidates.append(tokenizer_limit)
    if not candidates:
        for obj in (config, getattr(config, "text_config", None)):
            value = getattr(obj, "sliding_window", None) if obj is not None else None
            if isinstance(value, int) and 0 < value < 10_000_000:
                candidates.append(value)
    if not candidates:
        raise ValueError("could not determine a finite model context limit")
    return min(candidates)


def conversation_messages(mode: str, prompt_path: Path, history: list[dict]) -> list[dict]:
    system_prompt = system_prompt_for_mode(mode, prompt_path)
    return ([] if system_prompt is None else [{"role": "system", "content": system_prompt}]) + history


def rendered_token_count(tokenizer: Any, messages: list[dict], add_generation_prompt: bool = False) -> int:
    ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=add_generation_prompt)
    return len(ids)


def normalize_free_chat_generation_config(model: Any) -> None:
    """Avoid inherited max_length competing with explicit max_new_tokens."""
    model.generation_config.max_length = None


class SessionWriter:
    def __init__(self, path: Path | None, metadata: dict):
        self.path = path
        self.handle = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = path.open("x", encoding="utf-8", newline="\n")
            self._write({"type": "session", **metadata})

    def _write(self, row: dict) -> None:
        assert self.handle is not None
        self.handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.handle.flush()

    def message(self, item: dict) -> None:
        if self.handle is not None:
            self._write({"type": "message", **item})

    def close(self) -> None:
        if self.handle is not None:
            self.handle.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Text-only local chat; no model or session data is written by default.")
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--mode", choices=["minimal", "canonical"], required=True)
    parser.add_argument("--adapter", type=Path, help="Optional existing PEFT LoRA adapter directory")
    parser.add_argument("--save-session", type=Path, help="Create a new UTF-8 JSONL session log")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--repetition-penalty", type=float)
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--seed", type=int)
    return parser


def print_help() -> None:
    print("/status  model, context, generation, and GPU memory")
    print("/history current user/assistant history")
    print("/reset   clear history without reloading the model")
    print("/help    command list")
    print("/exit or /quit  exit and release GPU memory")


def main() -> None:
    configure_utf8_console()
    args = build_parser().parse_args()
    common, model_cfg, generation = load_settings(args.common, args.model_config, args)
    prompt_path = Path(common["canonical_system_prompt"])
    local_model_path = Path(model_cfg["model_path"])
    if not local_model_path.is_dir():
        raise SystemExit(f"local model directory does not exist: {local_model_path}")
    validate_adapter(args.adapter, local_model_path)
    if args.save_session is not None and args.save_session.exists():
        raise SystemExit(f"refusing to overwrite existing session log: {args.save_session}")

    tokenizer = AutoTokenizer.from_pretrained(
        local_model_path, local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
    )
    config = AutoConfig.from_pretrained(local_model_path, local_files_only=True, trust_remote_code=False)
    context_limit = model_context_limit(config, tokenizer)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForImageTextToText.from_pretrained(
        local_model_path,
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=quantization,
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    if args.adapter is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    normalize_free_chat_generation_config(model)
    model.eval()

    prompt_hash = None
    if args.mode == "canonical":
        prompt_hash = hashlib.sha256(system_prompt_for_mode(args.mode, prompt_path).encode("utf-8")).hexdigest()
    writer = SessionWriter(args.save_session, {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": model_cfg["model_id"],
        "model_revision": model_cfg["model_revision"],
        "model_local_path": str(local_model_path),
        "mode": args.mode,
        "canonical_prompt_sha256": prompt_hash,
        "adapter_path": None if args.adapter is None else str(args.adapter),
        "generation": generation,
        "context_limit": context_limit,
    })
    history: list[dict] = []
    turn = 0
    try:
        print("SHION Local Chat")
        print("Model: Ministral 3 8B Instruct")
        print(f"Mode: {args.mode}")
        print(f"Adapter: {'none' if args.adapter is None else args.adapter}")
        print(f"Generation: {generation}")
        print(f"Context limit: {context_limit} tokens | Vision input: unsupported")
        print("Session log: NO SESSION LOG" if args.save_session is None else f"Session log: {args.save_session}")
        print("Type /help for commands.\n")
        while True:
            try:
                user_text = input("You > ").strip()
            except EOFError:
                print()
                break
            if not user_text:
                continue
            command = user_text.lower()
            if command in {"/exit", "/quit"}:
                break
            if command == "/help":
                print_help()
                continue
            if command == "/reset":
                history.clear()
                print("History cleared; model remains loaded.")
                continue
            if command == "/history":
                if not history:
                    print("(empty)")
                for item in history:
                    print(f"{item['role'].capitalize()} > {item['content']}")
                continue
            if command == "/status":
                messages = conversation_messages(args.mode, prompt_path, history)
                tokens = rendered_token_count(tokenizer, messages) if messages else 0
                allocated = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
                reserved = torch.cuda.memory_reserved() / 1024**2 if torch.cuda.is_available() else 0
                print(f"Model: {model_cfg['model_id']} @ {model_cfg['model_revision']}")
                print(f"Mode: {args.mode} | Adapter: {'none' if args.adapter is None else args.adapter}")
                print(f"Context: {tokens}/{context_limit} | Generation: {generation}")
                print(f"GPU memory: allocated={allocated:.0f} MiB, reserved={reserved:.0f} MiB")
                continue
            if command.startswith("/"):
                print("Unknown command. Type /help.")
                continue

            proposed = history + [{"role": "user", "content": user_text}]
            messages = conversation_messages(args.mode, prompt_path, proposed)
            input_tokens = rendered_token_count(tokenizer, messages, add_generation_prompt=True)
            projected = input_tokens + generation["max_new_tokens"]
            if projected > context_limit:
                print(f"Context limit exceeded ({input_tokens} + {generation['max_new_tokens']} > {context_limit}). Use /reset.")
                continue
            if projected >= int(context_limit * 0.9):
                print(f"Warning: projected context usage is near the limit ({projected}/{context_limit}).")

            batch = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True
            ).to(model.device)
            set_seed(generation["seed"] + turn)
            with torch.inference_mode():
                output_ids = model.generate(
                    **batch,
                    do_sample=True,
                    temperature=generation["temperature"],
                    top_p=generation["top_p"],
                    top_k=generation["top_k"],
                    repetition_penalty=generation["repetition_penalty"],
                    max_new_tokens=generation["max_new_tokens"],
                    pad_token_id=tokenizer.pad_token_id,
                )
            response = tokenizer.decode(output_ids[0, batch["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            user_item = {"role": "user", "content": user_text}
            assistant_item = {"role": "assistant", "content": response}
            history.extend((user_item, assistant_item))
            writer.message(user_item)
            writer.message(assistant_item)
            turn += 1
            print(f"\nAssistant > {response}\n")
    finally:
        writer.close()
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
