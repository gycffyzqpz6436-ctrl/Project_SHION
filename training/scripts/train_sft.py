"""Owner-gated QLoRA entry point. Do not run without explicit training approval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import Dataset
from transformers import (
    AutoModelForImageTextToText,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tokenize_assistant_only(tokenizer, messages: list[dict], max_length: int) -> dict:
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True)
    full_ids = encoded["input_ids"]
    if len(full_ids) > max_length:
        raise ValueError(f"record has {len(full_ids)} tokens, over max {max_length}; truncation is forbidden")
    labels = [-100] * len(full_ids)
    assistant_spans: list[tuple[int, int]] = []
    cursor = 0
    for message in messages:
        content = message["content"]
        start = rendered.find(content, cursor)
        if start < 0:
            raise ValueError("chat template did not preserve message content exactly")
        end = start + len(content)
        if message["role"] == "assistant":
            assistant_spans.append((start, end))
        cursor = end
    for token_index, (start, end) in enumerate(encoded["offset_mapping"]):
        if start == end:
            continue
        if any(start < span_end and end > span_start for span_start, span_end in assistant_spans):
            labels[token_index] = full_ids[token_index]
    if all(value == -100 for value in labels):
        raise ValueError("assistant-only mask contains no trainable token")
    return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}


class TokenizedDataset(Dataset):
    def __init__(self, rows: list[dict], tokenizer, max_length: int):
        self.rows = [tokenize_assistant_only(tokenizer, row["messages"], max_length) for row in rows]

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict:
        return self.rows[index]


class PadCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features: list[dict]) -> dict:
        ids = pad_sequence([torch.tensor(f["input_ids"]) for f in features], batch_first=True, padding_value=self.pad_token_id)
        masks = pad_sequence([torch.tensor(f["attention_mask"]) for f in features], batch_first=True, padding_value=0)
        labels = pad_sequence([torch.tensor(f["labels"]) for f in features], batch_first=True, padding_value=-100)
        return {"input_ids": ids, "attention_mask": masks, "labels": labels}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--owner-approved-training", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_training:
        raise SystemExit("Refusing to train: pass --owner-approved-training only after explicit Owner approval")
    common, model_cfg = read_yaml(args.common), read_yaml(args.model_config)
    set_seed(common["seed"])
    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["model_path"], local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
    )
    rows = load_records(Path(common["training_data"]))
    if args.smoke:
        rows = rows[:4]
    dataset = TokenizedDataset(rows, tokenizer, common["max_sequence_length"])
    qcfg = model_cfg["quantization"]
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=qcfg["type"],
        bnb_4bit_use_double_quant=qcfg["double_quantization"],
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForImageTextToText.from_pretrained(
        model_cfg["model_path"],
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=quantization,
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation=model_cfg["training"]["attention_implementation"],
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = model_cfg["lora"]
    model = get_peft_model(model, LoraConfig(
        r=lora["rank"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"],
        bias=lora["bias"], task_type="CAUSAL_LM", target_modules=lora["target_modules_regex"],
    ))
    train = model_cfg["training"]
    output = Path(common["output_root"]) / ("smoke" if args.smoke else "checkpoints")
    arguments = TrainingArguments(
        output_dir=str(output), num_train_epochs=train["epochs"], learning_rate=train["learning_rate"],
        per_device_train_batch_size=train["per_device_train_batch_size"],
        gradient_accumulation_steps=train["gradient_accumulation_steps"],
        optim=train["optimizer"], lr_scheduler_type=train["scheduler"], warmup_ratio=train["warmup_ratio"],
        weight_decay=train["weight_decay"], max_grad_norm=train["max_grad_norm"], bf16=True, fp16=False,
        tf32=True, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False}, save_strategy=train["save_strategy"],
        save_total_limit=train["save_total_limit"], logging_steps=train["logging_steps"],
        max_steps=2 if args.smoke else -1, report_to="none", seed=common["seed"], data_seed=common["seed"],
        remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=arguments, train_dataset=dataset, data_collator=PadCollator(tokenizer.pad_token_id))
    trainer.train()
    trainer.save_model(str(output / "final_adapter"))


if __name__ == "__main__":
    main()
