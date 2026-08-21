# SHION SFT / QLoRA Experiment 0002 — Gemma 4 Preparation

Status: **FEASIBILITY PASS WITH CAUTION; FULL TRAINING NOT AUTHORIZED**

Reviewed: 2026-08-21

The bounded RTX 5070 Runtime/Smoke Gate was completed on 2026-08-22. Functional
steps and adapter reload passed, but physical VRAM peaked at 11,920 of 12,227 MiB
and performance showed WDDM oversubscription. See the
[Training Feasibility Gate report](shion_sft_exp_0002_gemma4_feasibility.md).

## Fixed scope

- Experiment ID: `shion_sft_exp_0002`
- Training foundation: `google/gemma-4-12b-it`
- Fixed revision: `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`
- Local path: `D:/AI/Project_SHION/models/experimental/gemma-4-12b-it`
- Architecture: `Gemma4UnifiedForConditionalGeneration`
- Data: the existing 200 Owner-approved Golden records, derived without body
  edits and with no injected system prompt
- Method under review: 4-bit NF4 QLoRA, double quantization, BF16 compute,
  assistant-only loss, no packing, reject rather than truncate

The Heretic JA v2 model is not the training foundation. No model weights,
Golden content, Canonical Documentation, Database body, private conversation, or
Experiment 0001 output is changed by this preparation.

## Static validation evidence

The pinned local repository loads offline with `local_files_only=True` and
`trust_remote_code=False` as `Gemma4UnifiedConfig` plus `GemmaTokenizer`. The
installed training stack is Transformers 5.14.1, PyTorch 2.11.0+cu128, PEFT
0.20.0, and bitsandbytes 0.50.0.

The official Gemma 4 chat template renders user turns as `<|turn>user` and
assistant turns as `<|turn>model`, terminated by `<turn|>`. Config EOS is
`[1, 106]`; runtime evaluation has an additional Gemma-specific stop token in its
separate generation policy. Training does not generate text, so mask correctness
is the relevant gate.

Running the existing exact-offset `tokenize_assistant_only` implementation over
all 200 derived records produced a non-empty assistant mask for every record:

| Check | Result |
|---|---:|
| Records / unique IDs | 200 / 200 |
| ID range | `shion_000101`–`shion_000300` |
| Gemma 4 tokens | min 46, mean 148.6, max 290 |
| Longest record | `shion_000191` |
| Records over 1024 / 2048 | 0 / 0 |
| Trainable assistant tokens | min 24, max 256 |
| Derived training JSONL SHA-256 | `3111b8e1358692434c3f1b7db0e6376bbb6eee28d709c61a8b6e4e4674da4b9f` |

Therefore 1024 is the first-choice maximum sequence length and retains every
record without truncation. A smaller value would also fit this snapshot but is
not selected because future derived-format changes need margin.

## Proposed adapter boundary

LoRA should target only the Gemma text decoder attention projections:

```text
language_model.layers.<n>.self_attn.(q_proj|k_proj|v_proj|o_proj)
```

The exact qualified prefix must be enumerated from the quantized loaded model
before training. The vision tower, audio tower, multimodal projectors, token
embeddings, normalization layers, and `lm_head` must be excluded. The current
training entry point already uses `AutoModelForImageTextToText`, but its
Ministral-specific tokenizer argument and target regex must not be reused without
a Gemma-specific config and module-name assertion.

Initial hyperparameter candidate, subject to Smoke review:

- NF4 4-bit, double quantization, BF16; batch 1
- LoRA rank 8, alpha 16, dropout 0.10; attention projections only
- learning rate `5e-5`, three epochs, gradient accumulation 8
- paged AdamW 8-bit, cosine schedule, warmup 0.10
- max sequence length 1024, packing off, gradient checkpointing on,
  `use_cache=False`, SDPA
- epoch checkpoints; seed 3407

These are preparation values, not an approved Full Training config.

## RTX 5070 12 GB feasibility

Feasibility is **high risk and unproven**. Experiment 0001's smaller 8B model
already peaked at 11,791 MiB of 12,227 MiB during its two-step Smoke. Gemma 4 12B
adds materially more quantized weights and decoder state. The short observed
sequences help, but they do not prove sufficient headroom.

Required ordered gate:

1. offline config/tokenizer/module enumeration only;
2. 4-bit NF4 load with no optimizer and record baseline/peak/released VRAM;
3. one forward/backward/optimizer step using the longest record
   `shion_000191` at max length 1024;
4. two-step four-record Smoke, adapter save/reload, finite loss and module match;
5. Owner review of VRAM, temperature, power, step time and warnings;
6. only then prepare an Owner-manual Full Training command.

Stop on OOM, NaN/Inf, unexpected trainable modules, missing assistant labels,
checkpoint reload mismatch, or less than a practical VRAM safety margin. Do not
automatically offload layers, lower precision, change the base, or begin Full
Training.

## Evaluation plan

Reuse the fixed 36-prompt evaluation set and identical generation metadata for
baseline and adapter evaluation. Mode A uses the Canonical System Prompt; Mode B
uses no character-specific system prompt. The expected artifact is 72 responses
per evaluated checkpoint. Compare base versus adapter for SHION identity,
Japanese naturalness, generic-assistant tendency, semantic conversation gate,
phrase/repetition tendency, safety hard gate, technical correctness, and long
context continuity. Baseline and long evaluation remain Owner-manual GPU tasks.

## Open blockers before Full Training

- A production Gemma-specific Full Training config is not yet approved.
- Physical VRAM headroom is only about 307 MiB at the observed Gate peak and is
  not safe for an unqualified Full Training recommendation.
- WDDM oversubscription and measured step time imply an estimated 14–18 hour run;
  Owner must decide whether to accept that risk or authorize a separate bounded
  memory/runtime mitigation experiment.
- Experiment 0002 Full Training is not Owner-approved.
- Baseline artifact completion for Experiment 0001 was not evidenced in the
  repository and must not be assumed.
- Full Training command, output path, recovery policy, expected time, and stop
  conditions require a separate preflight after Smoke.

## Authorization boundary

This document authorizes no training, baseline, evaluation, model download,
model conversion, Golden/Database/Canonical modification, commit of generated
artifacts, or private-conversation use.
