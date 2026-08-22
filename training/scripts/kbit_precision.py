"""Auditable Project SHION precision policy for Gemma 4 k-bit LoRA training."""

from __future__ import annotations

from typing import Any

import torch


def is_norm_module(module: torch.nn.Module) -> bool:
    return "norm" in type(module).__name__.lower()


def prepare_gemma4_for_kbit_training_precision_aware(
    model: Any, *, gradient_checkpointing_kwargs: dict[str, Any] | None = None
) -> Any:
    """Freeze a 4-bit Gemma 4 base, retain BF16 embeddings, and upcast norms only.

    This intentionally mirrors the non-precision parts of PEFT 0.20.0
    ``prepare_model_for_kbit_training`` without its blanket cast of every
    non-Params4bit BF16/FP16 parameter. It must be re-audited on PEFT upgrades.
    """
    if type(model).__name__ != "Gemma4UnifiedForCausalLM":
        raise TypeError(f"precision-aware policy only supports Gemma4UnifiedForCausalLM, got {type(model).__name__}")
    if not getattr(model, "is_loaded_in_4bit", False):
        raise ValueError("precision-aware policy requires a 4-bit loaded model")
    kwargs = gradient_checkpointing_kwargs or {"use_reentrant": False}
    if kwargs.get("use_reentrant", False):
        raise ValueError("precision-aware policy requires non-reentrant gradient checkpointing")

    model.config.use_cache = False
    for parameter in model.parameters():
        parameter.requires_grad = False
    for module in model.modules():
        if is_norm_module(module):
            for parameter in module.parameters(recurse=False):
                if parameter.is_floating_point() and parameter.dtype != torch.float32:
                    parameter.data = parameter.data.to(torch.float32)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs=kwargs)
    return model
