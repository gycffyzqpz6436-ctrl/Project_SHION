"""Validation for server-owned, immutable LoRA adapter bindings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixedAdapterBinding:
    path: Path
    experiment_id: str
    expected_target_count: int
    status: str
    dataset: str
    epochs: int
    rank: int
    alpha: int
    dropout: float


def _normalized_path(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value))).replace("\\", "/")


def resolve_fixed_adapter(model_spec: dict, requested: Path | None, model_path: Path) -> FixedAdapterBinding | None:
    """Resolve and statically validate an allowlisted adapter before any GPU load."""
    fixed = model_spec.get("fixed_adapter")
    if fixed is None:
        return None
    if requested is not None:
        raise ValueError("this model alias uses a fixed server-side adapter; overrides are prohibited")

    path = Path(fixed["local_path"])
    config_path = path / "adapter_config.json"
    weights_path = path / "adapter_model.safetensors"
    manifest_path = path.parent / "manifest.json"
    for required in (path, config_path, weights_path, manifest_path):
        if not required.exists():
            raise ValueError(f"fixed adapter artifact is missing: {required}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_revision = model_spec["revision"]
    expected_targets = int(fixed["expected_target_count"])
    checks = (
        (config.get("peft_type") == "LORA", "adapter is not LoRA"),
        (config.get("inference_mode") is True, "adapter is not saved for inference"),
        (_normalized_path(config.get("base_model_name_or_path", "")) == _normalized_path(model_path),
         "adapter base reference does not match the allowlisted local base"),
        (manifest.get("status") == "PASS" and manifest.get("mode") == "full", "training manifest is not PASS/full"),
        (manifest.get("experiment_id") == fixed["experiment_id"], "experiment ID mismatch"),
        (manifest.get("model_id") == model_spec["repo_id"], "manifest base model ID mismatch"),
        (manifest.get("model_revision") == expected_revision, "manifest base revision mismatch"),
        (_normalized_path(manifest.get("adapter_path", "")) == _normalized_path(path), "manifest adapter path mismatch"),
        (manifest.get("lora", {}).get("expected_target_count") == expected_targets, "LoRA target count mismatch"),
        (manifest.get("record_count") == fixed["record_count"], "training record count mismatch"),
        (manifest.get("training", {}).get("epochs") == fixed["epochs"], "training epoch count mismatch"),
        (config.get("r") == fixed["rank"], "LoRA rank mismatch"),
        (config.get("lora_alpha") == fixed["alpha"], "LoRA alpha mismatch"),
        (config.get("lora_dropout") == fixed["dropout"], "LoRA dropout mismatch"),
        (config.get("target_modules") == manifest.get("lora", {}).get("target_modules_regex"),
         "LoRA target-module policy mismatch"),
    )
    for passed, message in checks:
        if not passed:
            raise ValueError(f"fixed adapter validation failed: {message}")
    return FixedAdapterBinding(
        path=path,
        experiment_id=fixed["experiment_id"],
        expected_target_count=expected_targets,
        status=fixed["status"],
        dataset=fixed["dataset"],
        epochs=int(fixed["epochs"]),
        rank=int(fixed["rank"]),
        alpha=int(fixed["alpha"]),
        dropout=float(fixed["dropout"]),
    )


def validate_loaded_adapter(model, binding: FixedAdapterBinding) -> None:
    """Fail closed when PEFT did not activate the exact expected LoRA topology."""
    configs = getattr(model, "peft_config", {})
    active = getattr(model, "active_adapter", None)
    if not configs or active not in configs:
        raise ValueError("fixed adapter did not become active")
    targets = sum(1 for name, _ in model.named_modules() if name.endswith(".lora_A.default"))
    if targets != binding.expected_target_count:
        raise ValueError(f"loaded LoRA target count is {targets}, expected {binding.expected_target_count}")
