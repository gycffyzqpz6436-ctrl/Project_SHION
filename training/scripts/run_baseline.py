"""Owner-run fixed baseline generator with resumable, atomic output handling."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml
from transformers import AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig, set_seed

from prompt_utils import system_prompt_for_mode


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_resume_prefix(partial: Path, evaluations: list[dict], mode: str) -> list[dict]:
    if not partial.exists():
        return []
    rows = read_jsonl(partial)
    if len(rows) > len(evaluations):
        raise ValueError("partial output has more rows than the fixed evaluation")
    for index, row in enumerate(rows):
        expected = evaluations[index]
        if row.get("eval_id") != expected["eval_id"] or row.get("mode") != mode:
            raise ValueError(f"partial output diverges at row {index + 1}")
        if row.get("prompt_sha256") != sha256_bytes(expected["user_prompt"].encode("utf-8")):
            raise ValueError(f"partial prompt hash diverges at row {index + 1}")
    return rows


def build_metadata(common: dict, model_cfg: dict, mode: str, eval_path: Path, prompt_path: Path, tokenizer) -> dict:
    generation = common["generation"]
    effective_prompt = system_prompt_for_mode(mode, prompt_path)
    return {
        "schema_version": "1.0.0",
        "experiment_id": common["experiment_id"],
        "artifact": "official_base_baseline",
        "model_id": model_cfg["model_id"],
        "model_revision": model_cfg["model_revision"],
        "model_local_path": model_cfg["model_path"],
        "adapter": None,
        "trust_remote_code": False,
        "local_files_only": True,
        "evaluation_mode": mode,
        "evaluation_count": 36,
        "evaluation_sha256": sha256_file(eval_path),
        "canonical_prompt_source_sha256": sha256_file(prompt_path),
        "effective_system_prompt_sha256": None if effective_prompt is None else sha256_bytes(effective_prompt.encode("utf-8")),
        "seed": generation["seed"],
        "per_prompt_seed_strategy": "seed_plus_zero_based_eval_index",
        "temperature": generation["temperature"],
        "top_p": generation["top_p"],
        "top_k": generation["top_k"],
        "repetition_penalty": generation["repetition_penalty"],
        "max_new_tokens": generation["max_new_tokens"],
        "generation_mode": "sampling",
        "dtype": "bfloat16",
        "quantization": "bitsandbytes_4bit_nf4_double_quant_bfloat16_compute",
        "chat_template_sha256": sha256_bytes(tokenizer.chat_template.encode("utf-8")),
        "tokenizer_fix_mistral_regex": True,
        "transformers_version": __import__("transformers").__version__,
        "torch_version": torch.__version__,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--mode", choices=["canonical", "minimal"], required=True)
    parser.add_argument("--resume", action="store_true", help="Continue a validated .partial file")
    parser.add_argument("--owner-approved-baseline", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_baseline:
        raise SystemExit("Refusing baseline generation without explicit Owner approval")

    common = yaml.safe_load(args.common.read_text(encoding="utf-8"))
    model_cfg = yaml.safe_load(args.model_config.read_text(encoding="utf-8"))
    if model_cfg["model_id"] != "mistralai/Ministral-3-8B-Instruct-2512-BF16":
        raise SystemExit("Baseline runner is locked to the approved Model A")
    if model_cfg.get("model_class") != "AutoModelForImageTextToText":
        raise SystemExit("Unexpected Model A class")

    eval_path = Path(common["evaluation_data"])
    prompt_path = Path(common["canonical_system_prompt"])
    evaluations = read_jsonl(eval_path)
    if len(evaluations) != 36 or len({item["eval_id"] for item in evaluations}) != 36:
        raise SystemExit("Fixed evaluation must contain exactly 36 unique IDs")

    output = Path(common["output_root"]) / "baseline" / f"ministral8b_{args.mode}.jsonl"
    partial = output.with_suffix(output.suffix + ".partial")
    manifest = output.with_suffix(".manifest.json")
    if output.exists() or manifest.exists():
        raise SystemExit(f"Refusing to overwrite completed output: {output}")
    if partial.exists() and not args.resume:
        raise SystemExit(f"Partial output exists; inspect it and rerun with --resume: {partial}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["model_path"], local_files_only=True, trust_remote_code=False, fix_mistral_regex=True
    )
    metadata = build_metadata(common, model_cfg, args.mode, eval_path, prompt_path, tokenizer)
    completed = load_resume_prefix(partial, evaluations, args.mode) if args.resume else []

    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForImageTextToText.from_pretrained(
        model_cfg["model_path"],
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=quantization,
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    system_prompt = system_prompt_for_mode(args.mode, prompt_path)
    generation = common["generation"]
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    file_mode = "a" if completed else "w"
    with partial.open(file_mode, encoding="utf-8", newline="\n") as handle:
        for index, item in enumerate(evaluations[len(completed) :], start=len(completed)):
            prompt_seed = generation["seed"] + index
            set_seed(prompt_seed)
            messages = ([] if system_prompt is None else [{"role": "system", "content": system_prompt}]) + [
                {"role": "user", "content": item["user_prompt"]}
            ]
            batch = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True
            ).to(model.device)
            with torch.inference_mode():
                ids = model.generate(
                    **batch,
                    do_sample=True,
                    temperature=generation["temperature"],
                    top_p=generation["top_p"],
                    top_k=generation["top_k"],
                    repetition_penalty=generation["repetition_penalty"],
                    max_new_tokens=generation["max_new_tokens"],
                    pad_token_id=tokenizer.pad_token_id,
                )
            response = tokenizer.decode(ids[0, batch["input_ids"].shape[1] :], skip_special_tokens=True)
            row = {
                "eval_id": item["eval_id"],
                "mode": args.mode,
                "prompt": item["user_prompt"],
                "prompt_sha256": sha256_bytes(item["user_prompt"].encode("utf-8")),
                "prompt_seed": prompt_seed,
                "response": response,
            }
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            print(f"[{index + 1:02d}/36] {item['eval_id']}", flush=True)

    final_rows = read_jsonl(partial)
    if len(final_rows) != 36:
        raise SystemExit(f"Incomplete baseline retained at {partial}: {len(final_rows)}/36")
    metadata.update({
        "response_count": len(final_rows),
        "response_jsonl_sha256": sha256_file(partial),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    manifest_tmp = manifest.with_suffix(manifest.suffix + ".tmp")
    manifest_tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(partial, output)
    os.replace(manifest_tmp, manifest)
    print(f"COMPLETE: {output}")
    print(f"MANIFEST: {manifest}")


if __name__ == "__main__":
    main()
