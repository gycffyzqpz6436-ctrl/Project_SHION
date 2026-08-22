# SHION SFT / QLoRA Experiment 0002 — Memory Profiling Gate

Status: **COMPLETE — FULL TRAINING NO-GO**

Executed: 2026-08-22

## Scope and fixed conditions

This bounded Gate profiled exactly one optimizer step for `shion_000191` (290
tokens) through the previously validated official text-only
`Gemma4UnifiedForCausalLM` path. It retained NF4 double quantization, BF16
compute, LoRA rank 8 / alpha 16 / dropout 0.10 on 184 q/k/v/o targets,
assistant-only loss, batch size 1, max length 512, gradient checkpointing,
`use_cache=False`, and `torch.optim.AdamW` at 5e-5. It performed no optimization,
Full Training, checkpoint save, or adapter save.

The local checkpoint remained pinned to `google/gemma-4-12b-it` revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`. Loading was offline with
`local_files_only=True` and `trust_remote_code=False`.

## Measured parameter inventory

The text-only runtime exposes 6,457,376,512 packed parameter elements. The base
parameter payload immediately after load was 7,464,779,264 bytes (7,118.97 MiB):

| Component | Logical elements | Actual dtype/storage | Actual payload |
|---|---:|---|---:|
| Quantized matrices | about 10,899,947,520 | 5,449,973,760 uint8 packed elements | 5,197.50 MiB |
| Non-quantized base parameters | 1,007,402,752 | BF16 | 1,921.47 MiB |
| Base total | 11,907,350,272 conceptual | mixed | 7,118.97 MiB |
| LoRA weights | 10,665,984 | FP32 | 40.69 MiB |
| LoRA gradients | 10,665,984 | FP32 | 40.69 MiB |
| AdamW state after first step | 21,332,336 elements / 1,104 tensors | FP32 | 81.38 MiB |

The theoretical raw 4-bit matrix payload is 5,197.50 MiB. Double-quant block
metadata is estimated at roughly 162 MiB from one byte per 64-weight first-level
scale plus small second-level metadata. The measured gap between base parameter
payload and CUDA allocation was 165.72 MiB, but that gap also contains runtime
objects; it is therefore a corroborating upper-bound, not a pure metadata
measurement.

Optimizer construction allocated no state. The first AdamW step lazily created
368 state entries and 1,104 FP32 tensors. Their measured 81.38 MiB agrees with
two FP32 moments per trainable parameter plus small scalar step tensors.

## Stage timeline

All Torch readings were taken after `torch.cuda.synchronize()`. Stage-local peak
counters were reset after each observation. NVIDIA usage was sampled continuously
at 200 ms and at every boundary.

| Stage | Allocated MiB | Reserved MiB | Local peak allocated MiB | NVIDIA MiB |
|---|---:|---:|---:|---:|
| A. CUDA initial | 0.00 | 0 | 0.00 | 528 |
| B. NF4 base loaded | 7,284.69 | 7,440 | 7,372.26 | 8,010 |
| C. LoRA attached / k-bit prepared | 9,246.84 | 11,210 | 11,124.69 | 11,652 |
| D. training + checkpointing ready | 9,246.84 | 11,210 | 9,246.84 | 11,652 |
| E. optimizer created | 9,246.84 | 11,210 | 9,246.84 | 11,652 |
| F. 290-token batch on GPU | 9,246.85 | 11,210 | 9,246.85 | 11,652 |
| G. forward complete | 10,341.38 | 11,214 | 10,345.63 | 11,668 |
| H. backward complete | 9,604.05 | 11,254 | **10,921.38** | 11,716 |
| I. before optimizer step | 9,604.05 | 11,254 | 9,604.05 | 11,716 |
| J. optimizer step complete | 9,685.42 | **11,372** | 9,726.11 | **11,834** |
| K. zero_grad(set_to_none) | 9,644.74 | 11,372 | 9,685.42 | 11,834 |
| L. in-process cleanup | 56.94 | 7,166 | 9,644.74 | 7,628 |

Process-boundary cleanup returned NVIDIA usage to 379 MiB with zero utilization.
In-process residual reservation is allocator/process lifetime state, not a saved
model or surviving training process.

## What dominates memory

The most important finding is that `prepare_model_for_kbit_training` in the
installed PEFT version explicitly casts every non-`Params4bit` BF16/FP16
parameter to FP32. The measured non-quantized base payload is 1,921.47 MiB in
BF16. Its doubling plus 40.69 MiB of LoRA weights explains essentially the whole
1,962.16 MiB B-to-C allocation increase. Calling this stage “LoRA overhead” alone
would therefore be misleading.

Forward retained about 1,094.53 MiB over the batch-ready baseline and reached a
1,098.78 MiB local increment. Backward had about 580.00 MiB of additional
stage-local transient allocation above the retained forward level. These are
activation/recomputation/temporary-buffer estimates from boundary deltas, not a
complete tensor attribution. The 290-token batch itself was only 6,960 bytes.

At K, the allocator reported 9,644 MiB active, 11,372 MiB reserved, and about
1,651 MiB non-releasable memory. It reported zero CUDA OOMs, zero `cudaMalloc`
retries, and no oversize allocations. Fragmentation/non-releasable reservation is
material, but the measured FP32 preparation expansion and base payload are more
directly actionable.

Ranking based on this run:

| Factor | Rank | Evidence |
|---|---|---|
| Base mixed NF4/BF16 payload | Critical | 7,118.97 MiB payload; 7,284.69 MiB allocated |
| Blanket non-4-bit BF16-to-FP32 preparation | Critical | explains about 1,921.47 MiB of B-to-C growth |
| Activations/recomputation/temporary buffers | High | about 1,099 MiB forward and 580 MiB backward transient |
| CUDA reserved/non-releasable memory | High | 11,372 MiB reserved; about 1,651 MiB non-releasable |
| WDDM physical-residency pressure | High | physical peak 11,834/12,227 MiB; only 393 MiB margin |
| Optimizer state | Low | 81.38 MiB measured |
| LoRA weights | Low | 40.69 MiB measured |
| Gradients | Low | 40.69 MiB measured |
| Batch tensors | Low | 6,960 bytes |

## WDDM interpretation and run variability

Torch allocated/reserved are CUDA virtual allocator accounting; NVIDIA usage is
physical device residency plus driver/context/background allocations. Under
Windows WDDM, virtual allocations may be paged between dedicated VRAM and shared
system memory. Consequently the earlier unsliced Gate could report a 16.47 GiB
Torch peak while physical NVIDIA residency remained about 11.9 GiB. The excess
cannot be resident simultaneously on a 12,227 MiB board and is consistent with
WDDM eviction/shared-memory backing, but this run did not directly measure OS
shared-GPU bytes or page-fault counters, so their exact quantities are not
asserted.

This synchronized stage-by-stage run did **not** reproduce the earlier 16.47 GiB
Torch peak: its maximum stage-local allocation was 10,921 MiB and maximum
reservation was 11,372 MiB. Synchronization and shorter tensor lifetimes can
change overlap of temporary buffers, allocator reuse, and WDDM residency. This
observer effect and run-to-run WDDM state explain why the profile is suitable for
component ranking but does not invalidate the prior peak. Physical headroom was
still only 393 MiB, below the one-GiB safety target.

The optimizer step was stable with finite loss 4.669636, matching the Text-Only
Gate, and the synchronized forward/backward/step interval was 1.611 seconds in
this resident run. The large contrast with the prior 90.029-second spilled run is
further evidence that WDDM residency/paging state can dominate runtime; it is not
claimed as a durable speedup.

## Optimization candidates (not executed)

| Candidate | VRAM reduction | Quality impact | Runtime impact | Complexity |
|---|---|---|---|---|
| Precision-aware k-bit preparation: keep safe frozen non-quantized weights BF16 instead of blanket FP32 | High | Low expected; must be validated | Low/beneficial expected | Medium |
| Allocator tuning / fragmentation experiment | Medium | Low | Low/variable | Low |
| Paged or 8-bit optimizer | Low for this model (state only 81 MiB) | Low | Medium | Low |
| CPU optimizer offload | Low physical saving here | Low | High | Medium |
| Activation/checkpointing adjustment | Medium | Low–Medium | Medium–High | Medium |
| Reduce LoRA rank | Low | Medium | Low | Low |
| Reduce target modules | Low–Medium | High | Low | Low |
| Model CPU offload | High | Low | High | High |

The single recommended next experiment is a **precision-aware k-bit preparation
Gate**. It should isolate the PEFT BF16-to-FP32 preparation behavior while keeping
the Base, Dataset, LoRA rank/targets, optimizer, and batch fixed. The theoretical
upper bound is about 1,921 MiB less persistent allocation, likely enough to cross
the one-GiB margin target. Quality impact is expected low because these are frozen
base parameters, but numerical stability, tied embeddings/lm-head behavior, and
loss equivalence must be proven before any training approval. No such change was
made in this Gate.

**EXPERIMENT 0002 MEMORY PROFILE: COMPLETE**

**NEXT OPTIMIZATION: Precision-aware k-bit preparation Gate**

**FULL TRAINING: NO-GO**
