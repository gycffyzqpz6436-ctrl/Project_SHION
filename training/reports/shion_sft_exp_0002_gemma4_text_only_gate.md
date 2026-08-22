# SHION SFT / QLoRA Experiment 0002 — Text-Only Training Gate

Status: **PASS WITH CAUTION — FULL TRAINING NO-GO**

Executed: 2026-08-22

## Static compatibility

Transformers 5.14.1 officially provides `Gemma4UnifiedForCausalLM` and
`Gemma4UnifiedTextModel`. The downloaded checkpoint declares
`Gemma4UnifiedForConditionalGeneration`, with a nested
`Gemma4UnifiedTextConfig` and all language weights under
`model.language_model.*`. The text-only causal class expects the same tensors
under `model.*` and ties `lm_head.weight` to `model.embed_tokens.weight`.

Meta-device and Safetensors inspection established:

- 677 checkpoint keys total;
- 666 language-model keys;
- every language key maps one-to-one after removing `.language_model`;
- zero unexpected text keys;
- the only apparent expected-key absence is tied `lm_head.weight`;
- 11 explicit vision/audio keys are intentionally excluded;
- conceptual checkpoint parameters: 11,959,730,224;
- conceptual text-only parameters: 11,907,350,272;
- excluded multimodal parameters: 52,379,952 (about 0.44%).

The model was loaded directly from the unchanged local checkpoint using the
official `from_pretrained(key_mapping=...)` API:

```python
Gemma4UnifiedForCausalLM.from_pretrained(
    model_path,
    config=unified_config.text_config,
    key_mapping={r"^model\.language_model\.": "model."},
    local_files_only=True,
    trust_remote_code=False,
)
```

No conversion script, rewritten/merged checkpoint, custom code, monkey patch,
download, or weight save was required.

## Actual load and functional equivalence

- Actual class: `Gemma4UnifiedForCausalLM`.
- NF4, double quantization and BF16 compute: PASS.
- Load time: 63.537 seconds.
- Missing keys: 0.
- Mismatched keys: 0.
- Unexpected keys: the 11 known vision/audio tensors only.
- Runtime packed parameter count: 6,457,376,512.
- NF4 Torch allocated/reserved: 7,284.7 / 7,440 MiB.
- NF4 NVIDIA sample: 8,476 MiB.

The unchanged Gemma tokenizer/chat template generated one bounded Japanese
response for `こんにちは` in 3.015 seconds and 31 generated tokens. Generation
ended on an approved EOS, produced normal Japanese, and leaked no turn/channel
tokens. The text was generic Official-model assistant prose, which is acceptable
for this functional test and was not treated as a quality evaluation.

Config/chat behavior used tokenizer PAD 0 and explicit Gemma stop IDs
`[1, 106, 50]`. Loading and generation were fully offline with
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`, and
`trust_remote_code=False`.

## LoRA and Dataset

Actual text-only module enumeration found 184 targets under:

```text
model.layers.<0..47>.self_attn.(q_proj|k_proj|v_proj|o_proj)
```

LoRA rank 8, alpha 16, dropout 0.10, bias none attached successfully. Trainable
parameters were 10,665,984 of 6,468,042,496 runtime-visible PEFT parameters
(0.164903%). LoRA attachment used 9,255.0 MiB Torch allocated, 11,210 MiB
reserved, and 11,892 MiB in the NVIDIA completion sample.

All 200 Golden-derived records retained non-empty assistant-only masks at max
length 512. Length remained 46–290 tokens, mean 148.605, with zero truncation.

## Training gate

Longest record `shion_000191` (290 tokens):

- loss 4.669636, finite;
- forward/backward, gradient, and optimizer step: PASS;
- runtime: 90.029 seconds;
- Torch peak allocated/reserved: 16,471.0 / 16,820 MiB;
- NVIDIA completion sample: 11,507 MiB.

Four-record/two-step smoke used the same ordered records as the Unified 512 Gate:

| Step | Records | Mean loss | Runtime |
|---|---|---:|---:|
| 1 | `shion_000106` (46), `shion_000166` (148) | 5.888950 | 28.860 s |
| 2 | `shion_000288` (262), `shion_000191` (290) | 5.296328 | 76.149 s |

Two-step total was 105.009 seconds. OOM, CUDA error, NaN, and Inf were absent.
Smoke Torch peak allocated/reserved was 16,598.9 / 17,562 MiB. Overall physical
NVIDIA peak was 11,899 of 12,227 MiB, leaving approximately 328 MiB. Maximum
temperature/power was 59 C / 96.22 W; the power maximum occurred during the
separate functional generation check.

## Unified 512 versus text-only 512

Raw NVIDIA samples include changing desktop/background allocations. Torch values
and overall physical peaks are the primary like-for-like evidence.

| Metric | Unified | Text-only | Difference |
|---|---:|---:|---:|
| Conceptual checkpoint params | 11,959,730,224 | 11,907,350,272 | -52,379,952 |
| Runtime packed base params | 6,487,883,776 | 6,457,376,512 | -30,507,264 |
| NF4 Torch allocated | 7,323.6 MiB | 7,284.7 MiB | -38.9 MiB |
| NF4 NVIDIA sample | 9,757 MiB | 8,476 MiB | -1,281 MiB raw |
| LoRA Torch allocated | 9,302.2 MiB | 9,255.0 MiB | -47.3 MiB |
| LoRA NVIDIA sample | 11,925 MiB | 11,892 MiB | -33 MiB |
| Training/overall NVIDIA peak | 11,925 MiB | 11,899 MiB | -26 MiB |
| Physical margin | 302 MiB | 328 MiB | +26 MiB |
| Longest Torch peak allocated | 16,474.7 MiB | 16,471.0 MiB | -3.7 MiB |
| Longest Torch peak reserved | 16,814 MiB | 16,820 MiB | +6 MiB |
| Smoke Torch peak allocated | 16,611.7 MiB | 16,598.9 MiB | -12.8 MiB |
| Smoke Torch peak reserved | 17,596 MiB | 17,562 MiB | -34 MiB |
| WDDM spill | Yes | Yes | Not resolved |
| One-step runtime | 136.154 s | 90.029 s | -46.125 s (-33.9%) |
| Two-step runtime | 474.773 s | 105.009 s | -369.764 s (-77.9%) |
| Longest loss | 4.660094 | 4.669636 | +0.009542, not quality-significant |

Text-only loading provides a real and substantial runtime improvement, while
model-resident memory improves only by about 39–47 MiB. Physical peak improves by
only 26 MiB and remains within 328 MiB of the GPU limit. Torch reservation still
reaches 17.56 GiB, so WDDM oversubscription is not resolved.

## Cleanup and decision

The successful bounded process exited normally. Process-boundary verification
showed 236 MiB used, 11,708 MiB free, 0% utilization and no residual Gate process.
No adapter, checkpoint, model, or measurement JSON was added to Git.

Functional equivalence, LoRA attachment, Dataset integrity, training stability,
and runtime improvement pass. The required safe physical margin and spill removal
do not pass. Text-only is the technically preferred Experiment 0002 training
path, but it does not make Full Training safe enough for a GO recommendation on
the current Windows/RTX 5070 12 GB environment.

**EXPERIMENT 0002 TEXT-ONLY GATE: PASS WITH CAUTION**

**FULL TRAINING RECOMMENDATION: NO-GO**
