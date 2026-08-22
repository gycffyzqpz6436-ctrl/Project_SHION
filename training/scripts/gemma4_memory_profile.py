"""Bounded Owner-approved Gemma 4 text-only QLoRA memory profiling gate.

This entry point performs exactly one optimizer step on shion_000191. It is not
a general training command and deliberately exposes no epoch or step controls.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoConfig, AutoTokenizer, BitsAndBytesConfig, Gemma4UnifiedForCausalLM

from training.scripts.gemma4_feasibility import NvidiaMonitor, cuda_metrics, is_text_decoder_target, load_jsonl, make_batch
from training.scripts.train_sft import tokenize_assistant_only


TARGET_ID = "shion_000191"
MIB = 1024**2


def tensor_bytes(tensors: Iterable[torch.Tensor]) -> int:
    """Count tensor payload bytes, de-duplicating shared storage by data pointer."""
    seen: set[tuple[str, int]] = set()
    total = 0
    for tensor in tensors:
        if tensor is None:
            continue
        key = (str(tensor.device), tensor.data_ptr())
        if key not in seen:
            seen.add(key)
            total += tensor.numel() * tensor.element_size()
    return total


def tensor_inventory(tensors: Iterable[torch.Tensor]) -> dict[str, Any]:
    items = [tensor for tensor in tensors if tensor is not None]
    by_dtype: dict[str, dict[str, int]] = defaultdict(lambda: {"tensors": 0, "elements": 0, "bytes": 0})
    for tensor in items:
        entry = by_dtype[str(tensor.dtype)]
        entry["tensors"] += 1
        entry["elements"] += tensor.numel()
        entry["bytes"] += tensor.numel() * tensor.element_size()
    return {"tensor_count": len(items), "unique_bytes": tensor_bytes(items), "by_dtype": dict(by_dtype)}


def optimizer_tensors(optimizer: torch.optim.Optimizer) -> list[torch.Tensor]:
    return [value for state in optimizer.state.values() for value in state.values() if torch.is_tensor(value)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--owner-approved-memory-profile", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_memory_profile:
        raise SystemExit("Refusing GPU profiling without --owner-approved-memory-profile")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "memory_profile.json"
    result: dict[str, Any] = {
        "status": "FAIL",
        "scope": "one optimizer step only",
        "model_path": str(args.model_path),
        "data": str(args.data),
        "record_id": TARGET_ID,
        "max_sequence_length": 512,
        "quantization": {"type": "NF4", "double_quant": True, "compute_dtype": "bfloat16"},
        "lora": {"rank": 8, "alpha": 16, "dropout": 0.10, "targets": "q/k/v/o"},
        "optimizer": {"type": "torch.optim.AdamW", "lr": 5e-5},
        "stages": {},
        "errors": [],
    }
    monitor = NvidiaMonitor()
    model = optimizer = tokenizer = batch = output = loss = None
    stage_sample_start = 0

    def record_stage(key: str, *, reset_peaks_after: bool = False, extra: dict[str, Any] | None = None) -> None:
        nonlocal stage_sample_start
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        sample = NvidiaMonitor.sample()
        monitor.samples.append(sample)
        window = monitor.samples[stage_sample_start:]
        result["stages"][key] = {
            **cuda_metrics(),
            "nvidia": sample,
            "nvidia_window_peak_mib": max((item["memory_mib"] for item in window), default=sample["memory_mib"]),
            **(extra or {}),
        }
        stage_sample_start = len(monitor.samples)
        if reset_peaks_after and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

    monitor.start()
    try:
        record_stage("A_cuda_initial", reset_peaks_after=True)
        tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True, trust_remote_code=False)
        rows = load_jsonl(args.data)
        row = next(item for item in rows if item["id"] == TARGET_ID)
        encoded = tokenize_assistant_only(tokenizer, row["messages"], 512)
        if len(encoded["input_ids"]) != 290 or not any(label != -100 for label in encoded["labels"]):
            raise RuntimeError("longest record identity, token length, or assistant-only mask changed")

        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        config = AutoConfig.from_pretrained(args.model_path, local_files_only=True, trust_remote_code=False)
        started = time.perf_counter()
        model, loading_info = Gemma4UnifiedForCausalLM.from_pretrained(
            args.model_path,
            config=config.text_config,
            local_files_only=True,
            trust_remote_code=False,
            key_mapping={r"^model\.language_model\.": "model."},
            output_loading_info=True,
            quantization_config=quantization,
            device_map={"": 0},
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
        )
        if loading_info["missing_keys"] or loading_info["mismatched_keys"]:
            raise RuntimeError(f"text-only loading incompatibility: {loading_info}")
        base_inventory = tensor_inventory(model.parameters())
        record_stage(
            "B_nf4_base_loaded",
            reset_peaks_after=True,
            extra={
                "seconds": time.perf_counter() - started,
                "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                "parameter_inventory": base_inventory,
                "unexpected_keys": sorted(loading_info["unexpected_keys"]),
            },
        )

        targets = [name for name, _ in model.named_modules() if is_text_decoder_target(name)]
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model = get_peft_model(
            model,
            LoraConfig(
                r=8,
                lora_alpha=16,
                lora_dropout=0.10,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=r"^model\.layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)$",
            ),
        )
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        record_stage(
            "C_lora_attached",
            reset_peaks_after=True,
            extra={
                "target_count": len(targets),
                "trainable_parameter_count": sum(parameter.numel() for parameter in trainable),
                "trainable_inventory": tensor_inventory(trainable),
            },
        )

        model.train()
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        record_stage(
            "D_training_checkpointing_ready",
            reset_peaks_after=True,
            extra={"training": model.training, "gradient_checkpointing": model.is_gradient_checkpointing},
        )

        optimizer = torch.optim.AdamW(trainable, lr=5e-5)
        record_stage(
            "E_optimizer_created",
            reset_peaks_after=True,
            extra={"state_entries": len(optimizer.state), "state_inventory": tensor_inventory(optimizer_tensors(optimizer))},
        )

        batch = make_batch(tokenizer, row, 512, torch.device("cuda:0"))
        record_stage(
            "F_batch_on_gpu",
            reset_peaks_after=True,
            extra={"tokens": int(batch["input_ids"].numel()), "batch_inventory": tensor_inventory(batch.values())},
        )

        step_started = time.perf_counter()
        output = model(**batch)
        loss = output.loss
        if not torch.isfinite(loss):
            raise RuntimeError(f"non-finite loss: {loss.item()}")
        record_stage("G_forward_complete", reset_peaks_after=True, extra={"loss": float(loss.detach().cpu())})

        loss.backward()
        gradients = [parameter.grad for parameter in trainable if parameter.grad is not None]
        if not gradients:
            raise RuntimeError("no trainable gradients")
        record_stage(
            "H_backward_complete",
            reset_peaks_after=True,
            extra={"gradient_inventory": tensor_inventory(gradients)},
        )
        gradients = None
        record_stage("I_before_optimizer_step", reset_peaks_after=True)

        optimizer.step()
        record_stage(
            "J_optimizer_step_complete",
            reset_peaks_after=True,
            extra={
                "state_entries": len(optimizer.state),
                "state_inventory": tensor_inventory(optimizer_tensors(optimizer)),
                "step_seconds": time.perf_counter() - step_started,
            },
        )
        optimizer.zero_grad(set_to_none=True)
        record_stage(
            "K_zero_grad_complete",
            reset_peaks_after=True,
            extra={"remaining_gradient_count": sum(parameter.grad is not None for parameter in trainable)},
        )
        result["allocator_summary"] = torch.cuda.memory_summary(abbreviated=True)
        result["status"] = "PASS"
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        loss = output = batch = optimizer = model = tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        record_stage("L_cleanup")
        monitor.stop()
        result.update(monitor.maxima())
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
