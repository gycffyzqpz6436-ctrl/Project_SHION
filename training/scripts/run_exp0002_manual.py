"""Owner-manual Experiment 0002 Launch Gate, Full Training, and reload CLI.

Importing this module performs no CUDA initialization or model load. The launch
subcommand is permanently capped at five optimizer steps. Full Training requires
an explicit, separate approval flag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


LAUNCH_STEPS = 5
EXPECTED_POLICY = "gemma4_norm_fp32_tied_embedding_bf16"
EXPECTED_MODEL_CLASS = "Gemma4UnifiedForCausalLM"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("config root must be a mapping")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_config(config: dict[str, Any], *, mode: str) -> None:
    required = {
        "experiment_id": "shion_sft_exp_0002",
        "model_id": "google/gemma-4-12b-it",
        "model_revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        "max_sequence_length": 512,
        "assistant_only_loss": True,
        "packing": False,
        "local_files_only": True,
        "trust_remote_code": False,
    }
    for key, expected in required.items():
        if config.get(key) != expected:
            raise ValueError(f"unsafe config {key}: expected {expected!r}, got {config.get(key)!r}")
    training, lora, quantization, precision, guards = (
        config["training"], config["lora"], config["quantization"], config["precision"], config["guards"]
    )
    exact = {
        "learning_rate": 5e-5, "epochs": 3, "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8, "effective_batch_size": 8,
        "optimizer": "paged_adamw_8bit", "scheduler": "cosine", "warmup_ratio": 0.10,
        "weight_decay": 0.01, "max_grad_norm": 1.0, "gradient_checkpointing": True,
        "gradient_checkpointing_use_reentrant": False, "use_cache": False,
        "bf16": True, "fp16": False, "tf32": True, "attention_implementation": "sdpa",
        "save_strategy": "epoch", "save_total_limit": 3,
    }
    for key, expected in exact.items():
        if training.get(key) != expected:
            raise ValueError(f"unsafe training config {key}: expected {expected!r}, got {training.get(key)!r}")
    if {"rank": lora["rank"], "alpha": lora["alpha"], "dropout": lora["dropout"], "bias": lora["bias"], "expected_target_count": lora["expected_target_count"]} != {"rank": 8, "alpha": 16, "dropout": 0.10, "bias": "none", "expected_target_count": 184}:
        raise ValueError("unsafe LoRA configuration")
    if quantization != {"type": "nf4", "double_quantization": True, "compute_dtype": "bfloat16"}:
        raise ValueError("unsafe quantization configuration")
    if precision.get("policy") != EXPECTED_POLICY or "prepare_gemma4_for_kbit_training_precision_aware" not in precision.get("helper", ""):
        raise ValueError("precision-aware helper is not explicitly configured")
    if guards.get("launch_max_optimizer_steps") != LAUNCH_STEPS:
        raise ValueError("Launch Gate hard limit must be exactly 5")
    if mode == "launch" and LAUNCH_STEPS != 5:
        raise AssertionError("Launch Gate source hard limit changed")


def static_preflight(config_path: Path, *, mode: str) -> dict[str, Any]:
    config = read_config(config_path)
    validate_config(config, mode=mode)
    data_path = Path(config["training_data"])
    model_path = Path(config["model_path"])
    if not data_path.is_file() or not model_path.is_dir():
        raise FileNotFoundError("configured local Dataset or model directory is missing")
    actual_hash = sha256_file(data_path)
    if actual_hash != config["training_data_sha256"]:
        raise ValueError(f"training Dataset SHA-256 mismatch: {actual_hash}")
    rows = load_jsonl(data_path)
    if len(rows) != config["guards"]["expected_record_count"] or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("training Dataset count or unique-ID invariant failed")
    return {"config": config, "config_sha256": sha256_file(config_path), "dataset_sha256": actual_hash, "record_count": len(rows)}


def full_approval_guard(mode: str, approved: bool) -> None:
    if mode == "full" and not approved:
        raise SystemExit("Refusing Full Training: pass --owner-approved-full-training only after explicit Owner approval")


def disk_guard(output_root: Path, minimum_gib: float) -> dict[str, float]:
    usage = shutil.disk_usage(output_root.anchor or output_root)
    free_gib = usage.free / 1024**3
    if free_gib < minimum_gib:
        raise RuntimeError(f"insufficient disk space: {free_gib:.2f} GiB free, {minimum_gib:.2f} GiB required")
    return {"free_gib": free_gib, "minimum_gib": minimum_gib}


def nvidia_sample(*, strict: bool = False) -> dict[str, Any]:
    try:
        command = ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total,temperature.gpu,power.draw", "--format=csv,noheader,nounits"]
        values = subprocess.check_output(command, text=True, timeout=5).strip().splitlines()[0].split(",")
        name, used, free, total, temperature, power = (value.strip() for value in values)
        sample: dict[str, Any] = {"name": name, "used_mib": float(used), "free_mib": float(free), "total_mib": float(total), "temperature_c": float(temperature), "power_w": float(power)}
        try:
            process_output = subprocess.check_output(
                ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
                text=True,
                timeout=5,
            ).strip()
            sample["compute_processes"] = process_output.splitlines() if process_output else []
        except Exception as process_exc:
            sample["process_monitoring_warning"] = f"{type(process_exc).__name__}: {process_exc}"
        return sample
    except Exception as exc:
        if strict:
            raise RuntimeError(f"GPU preflight monitoring failed: {exc}") from exc
        return {"monitoring_error": f"{type(exc).__name__}: {exc}"}


def gpu_guard(config: dict[str, Any]) -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    sample = nvidia_sample(strict=True)
    if "RTX 5070" not in sample["name"]:
        raise RuntimeError(f"unexpected GPU: {sample['name']}")
    guards = config["guards"]
    if sample["used_mib"] > guards["maximum_preflight_gpu_used_mib"] or sample["free_mib"] < guards["minimum_preflight_gpu_free_mib"]:
        raise RuntimeError(f"GPU preflight refused: used={sample['used_mib']:.0f} MiB, free={sample['free_mib']:.0f} MiB; close GPU applications manually")
    return sample


def make_run_dir(config: dict[str, Any], mode: str, resume: Path | None) -> Path:
    if resume is not None:
        if not resume.is_dir() or not resume.name.startswith("checkpoint-"):
            raise ValueError("resume path must be an existing checkpoint-* directory")
        return resume.parent
    stamp = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    run_dir = Path(config["output_root"]) / ("launch_gate" if mode == "launch" else "full_training") / stamp
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite run directory: {run_dir}")
    return run_dir


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_training(config_path: Path, *, mode: str, approved: bool, resume: Path | None) -> None:
    full_approval_guard(mode, approved)
    preflight = static_preflight(config_path, mode=mode)
    config = preflight["config"]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    disk_minimum = config["guards"]["minimum_free_disk_gib_launch" if mode == "launch" else "minimum_free_disk_gib_full"]
    disk = disk_guard(Path(config["output_root"]), disk_minimum)
    gpu = gpu_guard(config)
    run_dir = make_run_dir(config, mode, resume)
    run_dir.mkdir(parents=True, exist_ok=resume is not None)
    metrics_path, manifest_path = run_dir / "metrics.json", run_dir / "manifest.json"
    previous_manifest: dict[str, Any] | None = None
    if resume is not None:
        if not manifest_path.is_file():
            raise FileNotFoundError("resume refused: parent run manifest is missing")
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous_manifest.get("mode") != "full" or previous_manifest.get("config_sha256") != preflight["config_sha256"] or previous_manifest.get("dataset_sha256") != preflight["dataset_sha256"]:
            raise ValueError("resume refused: mode/config/Dataset manifest mismatch")
    manifest: dict[str, Any] = {
        "schema_version": 1, "status": "RUNNING", "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(), "experiment_id": config["experiment_id"],
        "model_id": config["model_id"], "model_revision": config["model_revision"], "model_path": config["model_path"],
        "model_class": EXPECTED_MODEL_CLASS, "config_path": str(config_path), "config_sha256": preflight["config_sha256"],
        "dataset_path": config["training_data"], "dataset_sha256": preflight["dataset_sha256"], "record_count": preflight["record_count"],
        "precision_policy": config["precision"], "quantization": config["quantization"], "lora": config["lora"],
        "training": config["training"], "max_optimizer_steps": LAUNCH_STEPS if mode == "launch" else None,
        "disk_preflight": disk, "gpu_preflight": gpu, "output_dir": str(run_dir), "metrics_path": str(metrics_path),
        "resumed_from_checkpoint": str(resume) if resume else None,
    }
    if previous_manifest:
        manifest["original_created_at"] = previous_manifest.get("original_created_at", previous_manifest.get("created_at"))
    atomic_json(manifest_path, manifest)
    metrics: dict[str, Any] = {"status": "RUNNING", "steps": [], "monitoring_warnings": []}
    atomic_json(metrics_path, metrics)

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoConfig, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainerCallback, TrainingArguments, set_seed
    from training.scripts.gemma4_feasibility import is_text_decoder_target, lora_leaf_modules
    from training.scripts.gemma4_precision_gate import load_base
    from training.scripts.kbit_precision import prepare_gemma4_for_kbit_training_precision_aware
    from training.scripts.train_sft import PadCollator, TokenizedDataset

    class SafetyCallback(TrainerCallback):
        def __init__(self) -> None:
            self.grad_norm = None
            self.started = time.perf_counter()

        def on_pre_optimizer_step(self, args, state, control, model=None, **kwargs):
            squared = torch.zeros((), device="cuda")
            count = 0
            for parameter in model.parameters():
                if parameter.requires_grad and parameter.grad is not None:
                    if not torch.isfinite(parameter.grad).all():
                        raise FloatingPointError("non-finite gradient detected; stopping before optimizer step")
                    squared += parameter.grad.detach().float().pow(2).sum()
                    count += 1
            if count == 0:
                raise RuntimeError("no LoRA gradients detected")
            self.grad_norm = float(torch.sqrt(squared).cpu())
            if not math.isfinite(self.grad_norm):
                raise FloatingPointError("non-finite gradient norm detected")

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not logs or "loss" not in logs:
                return
            loss_value = float(logs["loss"])
            if not math.isfinite(loss_value):
                raise FloatingPointError("non-finite logged loss detected")
            sample = nvidia_sample(strict=False)
            if "monitoring_error" in sample:
                metrics["monitoring_warnings"].append(sample["monitoring_error"])
            torch_metrics = {"allocated_mib": torch.cuda.memory_allocated() / 1024**2, "reserved_mib": torch.cuda.memory_reserved() / 1024**2, "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2, "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2}
            item = {"step": int(state.global_step), "loss": loss_value, "grad_norm": self.grad_norm, "learning_rate": float(logs.get("learning_rate", 0.0)), "elapsed_seconds": time.perf_counter() - self.started, "torch": torch_metrics, "nvidia": sample}
            metrics["steps"].append(item)
            atomic_json(metrics_path, metrics)
            total = LAUNCH_STEPS if mode == "launch" else int(state.max_steps)
            print(f"[{state.global_step}/{total}] loss={loss_value:.6f} grad_norm={self.grad_norm:.6f} lr={item['learning_rate']:.8g} time={item['elapsed_seconds']:.1f}s", flush=True)

    class FiniteLossTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            value = super().compute_loss(model, inputs, return_outputs=return_outputs, num_items_in_batch=num_items_in_batch)
            loss_value = value[0] if return_outputs else value
            if not torch.isfinite(loss_value):
                raise FloatingPointError("non-finite loss detected")
            return value

    model = optimizer = trainer = None
    try:
        set_seed(config["seed"])
        tokenizer = AutoTokenizer.from_pretrained(config["model_path"], local_files_only=True, trust_remote_code=False)
        rows = load_jsonl(Path(config["training_data"]))
        dataset = TokenizedDataset(rows, tokenizer, config["max_sequence_length"])
        quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
        model, loading_info = load_base(Path(config["model_path"]), quantization)
        if loading_info["missing_keys"] or loading_info["mismatched_keys"]:
            raise RuntimeError("text-only base loading mismatch")
        model = prepare_gemma4_for_kbit_training_precision_aware(model, gradient_checkpointing_kwargs={"use_reentrant": False})
        targets = [name for name, _ in model.named_modules() if is_text_decoder_target(name)]
        lora = config["lora"]
        model = get_peft_model(model, LoraConfig(r=lora["rank"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"], bias=lora["bias"], task_type="CAUSAL_LM", target_modules=lora["target_modules_regex"]))
        if len(targets) != 184 or len(lora_leaf_modules(model)) != 184:
            raise RuntimeError("LoRA target count is not 184")
        train = config["training"]
        arguments = TrainingArguments(
            output_dir=str(run_dir), num_train_epochs=train["epochs"], max_steps=LAUNCH_STEPS if mode == "launch" else -1,
            learning_rate=train["learning_rate"], per_device_train_batch_size=1, gradient_accumulation_steps=8,
            optim=train["optimizer"], lr_scheduler_type=train["scheduler"], warmup_ratio=train["warmup_ratio"], weight_decay=train["weight_decay"], max_grad_norm=train["max_grad_norm"],
            bf16=True, fp16=False, tf32=True, gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
            save_strategy="no" if mode == "launch" else "epoch", save_total_limit=3, logging_strategy="steps", logging_steps=1, logging_first_step=True,
            eval_strategy="no", report_to="none", seed=config["seed"], data_seed=config["seed"], remove_unused_columns=False,
        )
        callback = SafetyCallback()
        trainer = FiniteLossTrainer(model=model, args=arguments, train_dataset=dataset, data_collator=PadCollator(tokenizer.pad_token_id), callbacks=[callback])
        torch.cuda.reset_peak_memory_stats()
        trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        if mode == "launch" and trainer.state.global_step != LAUNCH_STEPS:
            raise RuntimeError(f"Launch Gate did not stop at exactly 5 steps: {trainer.state.global_step}")
        adapter_dir = run_dir / ("adapter" if mode == "launch" else "final_adapter")
        trainer.save_model(str(adapter_dir))
        metrics["status"] = "PASS"
        nvidia_steps = [item["nvidia"] for item in metrics["steps"] if "used_mib" in item["nvidia"]]
        metrics["summary"] = {
            "completed_steps": trainer.state.global_step,
            "losses": [item["loss"] for item in metrics["steps"]],
            "grad_norms": [item["grad_norm"] for item in metrics["steps"]],
            "runtime_seconds": trainer.state.log_history[-1].get("train_runtime"),
            "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
            "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
            "nvidia_peak_used_mib": max((item["used_mib"] for item in nvidia_steps), default=None),
            "minimum_physical_margin_mib": min((item["free_mib"] for item in nvidia_steps), default=None),
            "max_temperature_c": max((item["temperature_c"] for item in nvidia_steps), default=None),
            "max_power_w": max((item["power_w"] for item in nvidia_steps), default=None),
            "nvidia_final": nvidia_sample(strict=False),
        }
        atomic_json(metrics_path, metrics)
        manifest.update({"status": "PASS", "completed_at": datetime.now(timezone.utc).isoformat(), "completed_steps": trainer.state.global_step, "adapter_path": str(adapter_dir), "adapter_files": sorted(path.name for path in adapter_dir.iterdir() if path.is_file()), "checkpoints": sorted(str(path) for path in run_dir.glob("checkpoint-*"))})
        atomic_json(manifest_path, manifest)
        print("\nOWNER REVIEW SUMMARY", json.dumps(metrics["summary"], ensure_ascii=False), f"\nmanifest={manifest_path}", flush=True)
    except Exception as exc:
        metrics.update({"status": "FAIL", "error": {"type": type(exc).__name__, "message": str(exc)}})
        manifest.update({"status": "FAIL", "failed_at": datetime.now(timezone.utc).isoformat(), "error_type": type(exc).__name__, "error_message": str(exc)})
        atomic_json(metrics_path, metrics); atomic_json(manifest_path, manifest)
        raise
    finally:
        model = optimizer = trainer = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache(); torch.cuda.ipc_collect()


def reload_adapter(manifest_path: Path) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or not manifest.get("adapter_path"):
        raise ValueError("manifest does not describe a completed adapter")
    preflight = static_preflight(Path(manifest["config_path"]), mode="launch" if manifest["mode"] == "launch" else "full")
    if preflight["config_sha256"] != manifest["config_sha256"] or preflight["dataset_sha256"] != manifest["dataset_sha256"]:
        raise ValueError("manifest/config/Dataset integrity mismatch")
    config = preflight["config"]
    disk_guard(Path(config["output_root"]), config["guards"]["minimum_free_disk_gib_launch"]); gpu_guard(config)
    import torch
    from peft import PeftModel
    from transformers import BitsAndBytesConfig
    from training.scripts.gemma4_feasibility import lora_leaf_modules
    from training.scripts.gemma4_precision_gate import load_base
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    base, loading_info = load_base(Path(config["model_path"]), quantization)
    model = PeftModel.from_pretrained(base, manifest["adapter_path"], local_files_only=True, is_trainable=False)
    targets = len(lora_leaf_modules(model)); active = bool(model.peft_config)
    if loading_info["missing_keys"] or targets != 184 or not active:
        raise RuntimeError("adapter reload validation failed")
    result = {"status": "PASS", "active": active, "target_count": targets, "base_reference": next(iter(model.peft_config.values())).base_model_name_or_path, "adapter_path": manifest["adapter_path"]}
    atomic_json(manifest_path.parent / "reload_validation.json", result)
    print("ADAPTER RELOAD PASS", json.dumps(result, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Owner-manual Experiment 0002 execution flow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="CPU/static validation only; never loads the model")
    validate.add_argument("--config", type=Path, required=True)
    launch = subparsers.add_parser("launch", help="exactly five optimizer steps; never continues to Full Training")
    launch.add_argument("--config", type=Path, required=True)
    full = subparsers.add_parser("full", help="three-epoch Full Training; explicit Owner approval required")
    full.add_argument("--config", type=Path, required=True)
    full.add_argument("--owner-approved-full-training", action="store_true")
    full.add_argument("--resume-from-checkpoint", type=Path)
    reload_parser = subparsers.add_parser("reload", help="offline adapter reload validation only")
    reload_parser.add_argument("--manifest", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "validate":
        result = static_preflight(args.config, mode="launch")
        print(json.dumps({key: value for key, value in result.items() if key != "config"}, indent=2))
    elif args.command == "launch":
        run_training(args.config, mode="launch", approved=False, resume=None)
    elif args.command == "full":
        run_training(args.config, mode="full", approved=args.owner_approved_full_training, resume=args.resume_from_checkpoint)
    else:
        reload_adapter(args.manifest)


if __name__ == "__main__":
    main()
