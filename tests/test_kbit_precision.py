from types import SimpleNamespace

import pytest
import torch

from training.scripts.kbit_precision import is_norm_module, prepare_gemma4_for_kbit_training_precision_aware


class Gemma4UnifiedForCausalLM(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(use_cache=True)
        self.is_loaded_in_4bit = True
        self.embed_tokens = torch.nn.Embedding(8, 4, dtype=torch.bfloat16)
        self.norm = torch.nn.LayerNorm(4, dtype=torch.bfloat16)
        self.lm_head = torch.nn.Linear(4, 8, bias=False, dtype=torch.bfloat16)
        self.lm_head.weight = self.embed_tokens.weight
        self.gc_kwargs = None

    def gradient_checkpointing_enable(self, gradient_checkpointing_kwargs):
        self.gc_kwargs = gradient_checkpointing_kwargs


def test_precision_policy_keeps_tied_embedding_bf16_and_norm_fp32():
    model = Gemma4UnifiedForCausalLM()
    pointer = model.embed_tokens.weight.data_ptr()
    prepare_gemma4_for_kbit_training_precision_aware(model)
    assert model.embed_tokens.weight.dtype == torch.bfloat16
    assert model.lm_head.weight.dtype == torch.bfloat16
    assert model.embed_tokens.weight.data_ptr() == pointer == model.lm_head.weight.data_ptr()
    assert model.norm.weight.dtype == torch.float32
    assert model.norm.bias.dtype == torch.float32
    assert not any(parameter.requires_grad for parameter in model.parameters())
    assert model.config.use_cache is False
    assert model.gc_kwargs == {"use_reentrant": False}


def test_precision_policy_rejects_reentrant_checkpointing():
    with pytest.raises(ValueError, match="non-reentrant"):
        prepare_gemma4_for_kbit_training_precision_aware(
            Gemma4UnifiedForCausalLM(), gradient_checkpointing_kwargs={"use_reentrant": True}
        )


def test_norm_detection_is_explicit():
    assert is_norm_module(torch.nn.LayerNorm(2))
    assert not is_norm_module(torch.nn.Linear(2, 2))
