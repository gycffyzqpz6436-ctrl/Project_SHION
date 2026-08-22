"""Bounded Owner-approved Gemma 4 QLoRA feasibility gate.

This is intentionally not a general training entry point. It performs exactly
one longest-record optimizer step, two four-record smoke optimizer steps, and an
adapter save/reload check. Full training is out of scope.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig

from training.scripts.train_sft import tokenize_assistant_only


EXPECTED_ARCHITECTURE = "Gemma4UnifiedForConditionalGeneration"
TARGET_SUFFIXES = ("q_proj", "k_proj", "v_proj", "o_proj")
FORBIDDEN_TARGET_PARTS = (
    "vision",
    "audio",
    "projector",
    "embed",
    "norm",
    "lm_head",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def choose_smoke_records(rows: list[dict[str, Any]], lengths: dict[str, int]) -> list[dict[str, Any]]:
    """Choose deterministic short, average, long, and longest records."""
    ordered = sorted(rows, key=lambda row: (lengths[row["id"]], row["id"]))
    mean = sum(lengths.values()) / len(lengths)
    average = min(ordered, key=lambda row: (abs(lengths[row["id"]] - mean), row["id"]))
    candidates = [ordered[0], average, ordered[-2], ordered[-1]]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates + ordered:
        if row["id"] not in seen:
            selected.append(row)
            seen.add(row["id"])
        if len(selected) == 4:
            break
    return selected


def is_text_decoder_target(name: str) -> bool:
    return (
        ".language_model.layers." in name
        and ".self_attn." in name
        and name.endswith(TARGET_SUFFIXES)
        and not any(part in name.lower() for part in FORBIDDEN_TARGET_PARTS)
    )


def lora_leaf_modules(model: Any) -> list[str]:
    """Return one concrete LoRA-A leaf per attached target, excluding ModuleDict containers."""
    return [name for name, _ in model.named_modules() if name.endswith(".lora_A.default")]


class NvidiaMonitor:
    def __init__(self) -> None:
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def sample() -> dict[str, float]:
        command = [
            "nvidia-smi",
            "--query-gpu=memory.used,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(command, text=True, timeout=5).strip().splitlines()[0]
        memory, temperature, power = (float(value.strip()) for value in output.split(","))
        return {"memory_mib": memory, "temperature_c": temperature, "power_w": power}

    def start(self) -> None:
        self.samples.append(self.sample())

        def poll() -> None:
            while not self._stop.wait(0.2):
                try:
                    self.samples.append(self.sample())
                except Exception:
                    pass

        self._thread = threading.Thread(target=poll, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        try:
            self.samples.append(self.sample())
        except Exception:
            pass

    def maxima(self) -> dict[str, float | None]:
        return {
            "nvidia_peak_memory_mib": max((s["memory_mib"] for s in self.samples), default=None),
            "max_temperature_c": max((s["temperature_c"] for s in self.samples), default=None),
            "max_power_w": max((s["power_w"] for s in self.samples), default=None),
        }


def cuda_metrics() -> dict[str, float]:
    return {
        "allocated_mib": torch.cuda.memory_allocated() / 1024**2,
        "reserved_mib": torch.cuda.memory_reserved() / 1024**2,
        "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
        "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
    }


def make_batch(tokenizer: Any, row: dict[str, Any], max_length: int, device: torch.device) -> dict[str, torch.Tensor]:
    encoded = tokenize_assistant_only(tokenizer, row["messages"], max_length)
    return {key: torch.tensor([value], dtype=torch.long, device=device) for key, value in encoded.items()}


def run_step(model: Any, optimizer: Any, batch: dict[str, torch.Tensor]) -> tuple[float, float, bool]:
    optimizer.zero_grad(set_to_none=True)
    started = time.perf_counter()
    output = model(**batch)
    loss = output.loss
    if not torch.isfinite(loss):
        raise RuntimeError(f"non-finite loss: {loss.item()}")
    loss.backward()
    gradient_exists = any(parameter.grad is not None for parameter in model.parameters() if parameter.requires_grad)
    if not gradient_exists:
        raise RuntimeError("no LoRA gradients were produced")
    optimizer.step()
    torch.cuda.synchronize()
    return float(loss.detach().cpu()), time.perf_counter() - started, gradient_exists


def unload(*objects: Any) -> None:
    for obj in objects:
        del obj
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-sequence-length", type=int, default=1024)
    parser.add_argument("--skip-adapter-save-reload", action="store_true")
    parser.add_argument("--owner-approved-feasibility-gate", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_feasibility_gate:
        raise SystemExit("Refusing GPU gate without --owner-approved-feasibility-gate")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = args.output_dir / "adapter"
    result_path = args.output_dir / "feasibility_result.json"
    result: dict[str, Any] = {
        "status": "FAIL",
        "model_path": str(args.model_path),
        "data": str(args.data),
        "max_sequence_length": args.max_sequence_length,
        "lora": {"rank": 8, "alpha": 16, "dropout": 0.10, "bias": "none"},
        "stages": {},
        "errors": [],
    }
    monitor = NvidiaMonitor()
    model = optimizer = tokenizer = reloaded = base = output = pair_losses = None
    monitor.start()
    result["before"] = {**monitor.samples[0], **cuda_metrics()}
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model_path, local_files_only=True, trust_remote_code=False
        )
        rows = load_jsonl(args.data)
        encoded = {
            row["id"]: tokenize_assistant_only(tokenizer, row["messages"], args.max_sequence_length)
            for row in rows
        }
        lengths = {record_id: len(value["input_ids"]) for record_id, value in encoded.items()}
        longest = max(rows, key=lambda row: (lengths[row["id"]], row["id"]))
        smoke_rows = choose_smoke_records(rows, lengths)
        result["records"] = {
            "longest": {"id": longest["id"], "tokens": lengths[longest["id"]]},
            "smoke": [{"id": row["id"], "tokens": lengths[row["id"]]} for row in smoke_rows],
        }

        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        model = AutoModelForImageTextToText.from_pretrained(
            args.model_path,
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            device_map={"": 0},
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
        )
        torch.cuda.synchronize()
        architecture = type(model).__name__
        if architecture != EXPECTED_ARCHITECTURE:
            raise RuntimeError(f"unexpected architecture: {architecture}")
        targets = [name for name, _ in model.named_modules() if is_text_decoder_target(name)]
        unexpected = [name for name in targets if any(part in name.lower() for part in FORBIDDEN_TARGET_PARTS)]
        if not targets or unexpected:
            raise RuntimeError(f"unsafe target enumeration: count={len(targets)}, unexpected={unexpected}")
        result["stages"]["nf4_load"] = {
            "success": True,
            "seconds": time.perf_counter() - started,
            "architecture": architecture,
            "target_modules": targets,
            "target_count": len(targets),
            **cuda_metrics(),
            "nvidia": NvidiaMonitor.sample(),
        }

        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        target_pattern = r"^model\.language_model\.layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)$"
        model = get_peft_model(
            model,
            LoraConfig(
                r=8,
                lora_alpha=16,
                lora_dropout=0.10,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=target_pattern,
            ),
        )
        trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
        total = sum(parameter.numel() for parameter in model.parameters())
        attached = lora_leaf_modules(model)
        if len(attached) != len(targets):
            raise RuntimeError(f"LoRA count mismatch: targets={len(targets)}, attached={len(attached)}")
        result["stages"]["lora_attach"] = {
            "success": True,
            "trainable_parameters": trainable,
            "total_parameters": total,
            "trainable_percent": trainable / total * 100,
            "attached_count": len(attached),
            **cuda_metrics(),
            "nvidia": NvidiaMonitor.sample(),
        }
        optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=5e-5)
        device = torch.device("cuda:0")

        torch.cuda.reset_peak_memory_stats()
        loss, seconds, gradient_exists = run_step(
            model, optimizer, make_batch(tokenizer, longest, args.max_sequence_length, device)
        )
        result["stages"]["longest_step"] = {
            "success": True,
            "loss": loss,
            "seconds": seconds,
            "gradient_exists": gradient_exists,
            **cuda_metrics(),
            "nvidia": NvidiaMonitor.sample(),
        }

        smoke_losses: list[float] = []
        smoke_times: list[float] = []
        torch.cuda.reset_peak_memory_stats()
        for first, second in ((smoke_rows[0], smoke_rows[1]), (smoke_rows[2], smoke_rows[3])):
            optimizer.zero_grad(set_to_none=True)
            started = time.perf_counter()
            pair_losses: list[torch.Tensor] = []
            for row in (first, second):
                output = model(**make_batch(tokenizer, row, args.max_sequence_length, device))
                if not torch.isfinite(output.loss):
                    raise RuntimeError(f"non-finite smoke loss for {row['id']}")
                (output.loss / 2).backward()
                pair_losses.append(output.loss.detach())
            optimizer.step()
            torch.cuda.synchronize()
            smoke_losses.append(float(torch.stack(pair_losses).mean().cpu()))
            smoke_times.append(time.perf_counter() - started)
        result["stages"]["smoke"] = {
            "success": True,
            "optimizer_steps": 2,
            "losses": smoke_losses,
            "step_seconds": smoke_times,
            "total_seconds": sum(smoke_times),
            **cuda_metrics(),
            "nvidia": NvidiaMonitor.sample(),
        }

        if args.skip_adapter_save_reload:
            result["stages"]["adapter_save_reload"] = {
                "skipped": True,
                "reason": "not required by bounded memory/runtime comparison",
            }
            result["status"] = "PASS"
            return

        model.save_pretrained(adapter_dir, safe_serialization=True)
        adapter_files = [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in sorted(adapter_dir.iterdir())
            if path.is_file()
        ]
        result["stages"]["adapter_save"] = {"success": True, "path": str(adapter_dir), "files": adapter_files}

        del optimizer
        optimizer = None
        del model
        model = None
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

        base = AutoModelForImageTextToText.from_pretrained(
            args.model_path,
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            device_map={"": 0},
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
        )
        reloaded = PeftModel.from_pretrained(base, adapter_dir, local_files_only=True, is_trainable=False)
        reloaded_attached = lora_leaf_modules(reloaded)
        active = bool(reloaded.peft_config) and len(reloaded_attached) == len(targets)
        base_reference = next(iter(reloaded.peft_config.values())).base_model_name_or_path
        if not active:
            raise RuntimeError("reloaded adapter is not active or target count changed")
        result["stages"]["adapter_reload"] = {
            "success": True,
            "active": active,
            "base_model_name_or_path": base_reference,
            "attached_count": len(reloaded_attached),
            **cuda_metrics(),
        }
        result["status"] = "PASS"
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        try:
            del optimizer, model, reloaded, base, tokenizer, output, pair_losses
        except Exception:
            pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        monitor.stop()
        result.update(monitor.maxima())
        result["after_cleanup"] = {**NvidiaMonitor.sample(), **cuda_metrics()}
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
