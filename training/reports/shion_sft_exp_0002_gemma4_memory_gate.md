# SHION SFT / QLoRA Experiment 0002 — Memory / Runtime Mitigation Gate

Status: **FAIL — FULL TRAINING NO-GO**

Executed: 2026-08-22

## Question and controlled variable

This bounded experiment tested whether changing only `max_sequence_length` from
1,024 to 512 would remove Windows WDDM oversubscription and create practical
physical VRAM headroom on the RTX 5070 12 GB. It used the same Official Gemma 4
12B IT revision, NF4/double-quant/BF16 settings, rank-8 attention-only LoRA,
assistant-only loss, AdamW, LR, gradient checkpointing, record order, and
optimizer-step structure as the prior Feasibility Gate.

No Full Training, adapter save/reload, generation, model change, rank/target/
optimizer/offload/batch change, or additional optimization trial was performed.

## Dataset gate

All 200 records were tokenized offline with the pinned Gemma tokenizer and a hard
512-token rejection limit:

| Metric | Result |
|---|---:|
| Records | 200 |
| Minimum | 46 tokens |
| Average | 148.605 tokens |
| Maximum | 290 tokens |
| Longest | `shion_000191` |
| Over 512 | 0 |
| Truncated | 0 |

The dataset loses no information at 512. However, the collator uses dynamic
single-record lengths and does not pad records to the configured maximum. The
actual tensors were therefore exactly the same lengths as in the 1,024 Gate.

## 512 runtime result

Environment and model identity remained unchanged: RTX 5070 12,227 MiB, PyTorch
2.11.0+cu128, Transformers 5.14.1, PEFT 0.20.0, bitsandbytes 0.50.0,
`google/gemma-4-12b-it` revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`, offline/local-only and
`trust_remote_code=False`.

- NF4 load: PASS in 69.067 seconds; Torch allocated/reserved
  7,323.6/7,454 MiB; NVIDIA sample 9,757 MiB.
- LoRA attach: PASS; 184 text-decoder targets, 10,665,984 trainable parameters;
  Torch allocated/reserved 9,302.2/11,338 MiB; NVIDIA sample 11,925 MiB.
- Longest one-step: loss 4.660094, finite; gradient and optimizer step PASS;
  136.154 seconds; Torch peak allocated/reserved 16,474.7/16,814 MiB;
  NVIDIA completion sample 11,915 MiB.
- Two-step smoke: losses 5.891754 and 5.299750, both finite; times 129.403 and
  345.370 seconds; total 474.773 seconds; Torch peak allocated/reserved
  16,611.7/17,596 MiB; NVIDIA completion sample 11,902 MiB.
- Overall NVIDIA peak: 11,925 of 12,227 MiB; physical margin approximately
  302 MiB.
- Maximum temperature/power: 58 C / 73.27 W.
- OOM, CUDA error, NaN/Inf: none.

Torch reservation again exceeded physical VRAM, so WDDM memory virtualization/
spill remained present. The successful Python process exited normally. Its
in-process cleanup sample retained the final forward output graph; this utility
reference was corrected afterward. Process-boundary verification showed 661 MiB
used, 11,283 MiB free, 6% utilization, and no residual Gate process.

## Controlled comparison

Raw NVIDIA values include different desktop/background baselines (906 MiB before
the 1,024 successful run versus 2,214 MiB before the 512 run). Torch measurements
are the cleaner like-for-like allocation comparison and are effectively
identical.

| Metric | 1024 | 512 | Difference |
|---|---:|---:|---:|
| Longest record tokens | 290 | 290 | 0 |
| Truncated records | 0 | 0 | 0 |
| NF4 Torch allocated | 7,323.6 MiB | 7,323.6 MiB | 0 |
| NF4 NVIDIA sample | 8,545 MiB | 9,757 MiB | +1,212 MiB raw |
| LoRA Torch allocated | 9,302.2 MiB | 9,302.2 MiB | 0 |
| LoRA NVIDIA sample | 11,894 MiB | 11,925 MiB | +31 MiB raw |
| NVIDIA overall peak | 11,920 MiB | 11,925 MiB | +5 MiB |
| Free physical VRAM at peak | 307 MiB | 302 MiB | -5 MiB |
| Longest Torch peak allocated | 16,474.7 MiB | 16,474.7 MiB | 0 |
| Longest Torch peak reserved | 16,816 MiB | 16,814 MiB | -2 MiB |
| Smoke Torch peak allocated | 16,612.2 MiB | 16,611.7 MiB | -0.5 MiB |
| Smoke Torch peak reserved | 17,598 MiB | 17,596 MiB | -2 MiB |
| WDDM oversubscription | Yes | Yes | Not resolved |
| One-step time | 128.415 s | 136.154 s | +7.739 s |
| Two-step total time | 383.418 s | 474.773 s | +91.355 s |
| Longest loss | 4.660094 | 4.660094 | 0 |
| Smoke losses | 5.891994 / 5.300570 | 5.891754 / 5.299750 | not quality-significant |
| Maximum temperature | 60 C | 58 C | -2 C |
| Maximum power | 77.96 W | 73.27 W | -4.69 W |

The loss differences are not evidence of quality improvement; this was a tiny
runtime Gate, not a deterministic training-quality comparison.

## Assessment

- Physical VRAM headroom: **FAIL** — 302 MiB, not the requested stable 1 GiB.
- WDDM oversubscription: **FAIL** — unchanged.
- Runtime improvement: **FAIL** — no improvement; measured time was slower.
- Training stability: **PASS** — all three optimizer steps remained finite.
- Dataset information loss: **PASS** — zero truncation.

Lowering only the configured maximum cannot reduce memory when every dynamically
batched input was already below 512 and no fixed-length padding was used. The
mitigation therefore does not make Full Training practical or safer on the
current Windows/RTX 5070 12 GB runtime.

Potential future experiments require a new Owner gate. Candidates may include a
single carefully selected change to LoRA rank/targets, optimizer/runtime memory,
or hardware/runtime placement. None was attempted here.

**EXPERIMENT 0002 MEMORY GATE: FAIL**

**FULL TRAINING RECOMMENDATION: NO-GO**
