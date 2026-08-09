# Training architecture — shion_sft_exp_0001

Owner policy permits only official Mistral AI base models for this experiment.
Third-party derivatives and models developed by Chinese companies or
organizations are excluded from training, baseline, smoke, fallback, and
comparison.

## Selected models

- Primary: `mistralai/Ministral-3-8B-Instruct-2512-BF16`, revision
  `f6fae9795746f63c9be8344932f01275f3c63734`, Apache-2.0.
- Download-only comparison: `mistralai/Mistral-Nemo-Instruct-2407`, revision
  `04d8a90549d23fc6bd7f642064003592df51e9b3`, Apache-2.0.

Both are official `mistralai` distributions. `consolidated.safetensors` was
excluded because the Transformers sharded weights are already complete.

## Execution environment

Native Windows is selected. Official PyTorch CUDA 12.8 and bitsandbytes 0.50
support the RTX 5070's `sm_120`; actual BF16 and NF4 CUDA tests passed. WSL is
not installed and would require an OS-level change/restart. Native execution
therefore has the lowest present risk and preserves the existing system.

Backend: Transformers 5.14.1 + PEFT 0.20.0, with TRL 1.9.2 installed but not
used for label construction. The official Mistral templates do not contain
`{% generation %}`, so TRL's automatic `assistant_only_loss` mask is empty.
`train_sft.py` instead maps exact rendered-character offsets back to tokens and
labels only assistant text. All 200 samples passed this mask validation.

Unsloth is not installed or selected. Native Windows/Ministral 3 support is not
required for this experiment because the standard stack works, is easier to
debug, and does not add another compatibility layer.

## Training design

- 4-bit NF4, double quantization, BF16 compute
- LoRA rank 8, alpha 16, dropout 0.10
- Attention projections only
- Regex restricted to
  `model.language_model.layers.<n>.self_attn.(q|k|v|o)_proj`
- This excludes the Mistral 3 vision tower and multimodal projector.
- LR 5e-5, three epochs, batch 1, accumulation 8
- max length 2048; reject rather than truncate
- packing off, gradient checkpointing on, `use_cache=false`
- SDPA attention, paged AdamW 8-bit, cosine schedule, 10% warmup
- checkpoints at epochs 1, 2, and 3

The 4-bit Model A load allocated about 5,921 MiB. Parameters, LoRA optimizer
state, activations, gradients, and CUDA workspace should place training near
8.5–11.5 GiB at batch 1/2048 depending on the longest batch. The smoke test is
mandatory before full training. An OOM requires reducing max length to the
observed dataset maximum (835 tokens) before changing learning settings.

## Sequence-length review after Smoke

The selected tokenizer measures the 200 derived records at 561–835 tokens
(mean 679.4, p95 772). Both 1024 and 2048 therefore retain every record without
truncation. Smoke peaked at 11,791/12,227 MiB using records no longer than 630
tokens, so 1024 is the first-choice Full Training limit for Owner review. The
config remains 2048 until that review and is not silently changed here. A
longest-record one-step check remains advisable before Full Training.

## System prompt experiment

Training does not inject the Canonical System Prompt. This is intentional for a
Dataset Health Check: it lets the adapter's learned personality be measured
without duplicating the prompt in every example.

Evaluation mode A applies the extracted implementation prompt from `# Identity`
through `# Closing Philosophy` to both baseline and fine-tuned models.
Evaluation mode B uses no character system prompt. This separates prompt-induced
identity from adapter-induced identity without rewriting canonical content.
