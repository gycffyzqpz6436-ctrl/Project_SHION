# SHION SFT / QLoRA Experiment 0002 — Training Feasibility Gate

Status: **PASS WITH CAUTION — FULL TRAINING NOT AUTHORIZED**

Executed: 2026-08-22

## Scope and environment

This bounded gate tested whether the fixed Official Gemma 4 12B IT foundation
can perform QLoRA optimizer steps on the Owner's RTX 5070 12 GB. It was not Full
Training, a benchmark, generation-quality evaluation, or a base-model review.

| Item | Value |
|---|---|
| Model | `google/gemma-4-12b-it` |
| Revision | `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` |
| Local model | `D:/AI/Project_SHION/models/experimental/gemma-4-12b-it` |
| Architecture | `Gemma4UnifiedForConditionalGeneration` |
| GPU | NVIDIA GeForce RTX 5070, 12,227 MiB |
| Driver / CUDA wheel | 591.74 / CUDA 12.8 |
| PyTorch | 2.11.0+cu128 |
| Transformers / PEFT / bitsandbytes | 5.14.1 / 0.20.0 / 0.50.0 |
| Offline policy | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` |
| Loading policy | `local_files_only=True`, `trust_remote_code=False` |

Initial GPU state was 906 MiB used, 52 C and 42.73 W for the successful run.
The earlier preflight observed 2,029 MiB used; no Owner process was terminated.

## Model and adapter gate

The Gemma tokenizer/chat template, assistant-only exact-offset mask, BF16 compute,
NF4, and double quantization passed. Config EOS is `[1, 106]`, tokenizer EOS is
1, PAD is 0, and the text context configuration supports far more than the
selected 1,024-token training limit.

Actual `named_modules()` enumeration found 184 eligible text-decoder attention
projections under:

```text
model.language_model.layers.<0..47>.self_attn.(q_proj|k_proj|v_proj|o_proj)
```

Some full-attention layers share K/V and therefore expose no separate `v_proj`;
the target count is 184 rather than 192. Vision, audio, projector, embedding,
normalization and `lm_head` modules were excluded and asserted absent.

LoRA configuration:

- rank 8, alpha 16, dropout 0.10, bias none;
- 184 attached targets;
- 10,665,984 trainable parameters;
- 6,498,549,760 parameters visible through the quantized PEFT model;
- 0.164129% trainable;
- gradient checkpointing enabled with `use_reentrant=False`;
- `use_cache=False`, SDPA, max sequence length 1,024;
- direct AdamW for this bounded Gate, LR `5e-5`.

## Runtime results

### NF4 and attachment

| Stage | Torch allocated | Torch reserved | NVIDIA total used |
|---|---:|---:|---:|
| NF4 load | 7,323.6 MiB | 7,454 MiB | 8,545 MiB |
| LoRA attached | 9,302.2 MiB | 11,338 MiB | 11,894 MiB |

NF4 load completed in 61.28 seconds. Attachment succeeded without OOM, but only
approximately 333 MiB remained at its sampled point.

### Longest-record one-step gate

- Record: `shion_000191`
- Tokens: 290
- Batch: 1; one record; one optimizer step; assistant-only loss
- Loss: 4.660094 (finite)
- Step time: 128.415 seconds
- Gradient: present
- Optimizer step: PASS
- CUDA/OOM/NaN/Inf: none
- NVIDIA sampled usage: 11,893 MiB
- Temperature/power at completion sample: 56 C / 58.28 W
- Torch step peak: 16,474.7 MiB allocated, 16,816 MiB reserved

The Torch values above exceed physical VRAM because Windows WDDM/driver memory
virtualization permitted allocation/spill. They must not be interpreted as real
VRAM headroom; `nvidia-smi` is the physical-device reference.

### Four-record / two-step smoke

| Role | Record | Tokens |
|---|---|---:|
| Short | `shion_000106` | 46 |
| Average | `shion_000166` | 148 |
| Long | `shion_000288` | 262 |
| Longest | `shion_000191` | 290 |

Two records were accumulated per optimizer step so all four selected records were
used in exactly two optimizer steps.

| Step | Mean loss | Time |
|---|---:|---:|
| 1 | 5.891994 | 89.460 s |
| 2 | 5.300570 | 293.958 s |

Total two-step time was 383.418 seconds. Both losses were finite; no OOM, NaN,
Inf, or CUDA error occurred. The overall physical GPU peak was 11,920 MiB of
12,227 MiB, leaving only about 307 MiB. Torch peak reserved reached 17,598 MiB,
again demonstrating WDDM oversubscription rather than safe capacity. Maximum
temperature was 60 C and maximum sampled power was 77.96 W.

## Adapter and cleanup

Only PEFT adapter artifacts were saved under the Gitignored external path:

`D:/AI/Project_SHION/training_output/shion_sft_exp_0002/feasibility_gate/adapter`

- `adapter_model.safetensors`: 42,718,528 bytes
- `adapter_config.json`: 1,208 bytes
- generated PEFT `README.md`: 5,262 bytes
- saved base reference: the fixed local Official Gemma 4 path
- offline PEFT reload: PASS
- active LoRA leaf modules after reload: 184, matching the original attachment

The in-process cleanup sample was taken before a lingering local `base` reference
was released, so it is not used as the final cleanup measurement. The utility was
corrected to release that reference. After the bounded Python process exited,
`nvidia-smi` showed 750 MiB used, 11,194 MiB free, 5% utilization, and no residual
Gate process. Cleanup therefore passed at the process boundary.

## Warnings and corrections

- The first invocation used the script file directly and stopped before model
  load because the repository package was not on `sys.path`. The validated entry
  point is `python -m training.scripts.gemma4_feasibility`.
- The first loaded attempt stopped before an optimizer step because the utility
  counted both PEFT `ModuleDict` containers and their leaf adapters. It was
  corrected to count only `.lora_A.default`; the actual attachment was valid.
- No memory-reduction mitigation, rank reduction, sequence reduction, data edit,
  model substitution, or GPU-process termination was performed.
- Triton was not installed; PyTorch reported only that Triton FLOP counting is
  unavailable. This did not block the Gate.

## Full Training recommendation

Do **not** start Full Training yet. The functional result passes, but physical
headroom is extreme and WDDM oversubscription makes step time impractical and OOM
risk sensitive to any concurrent GPU allocation.

If the Owner later approves a separate Full Training preflight, keep this initial
candidate rather than silently changing it:

- max sequence length 1,024; batch 1; no packing;
- gradient accumulation 8 (effective batch 8);
- rank 8, alpha 16, dropout 0.10;
- LR `5e-5`, three epochs, cosine, warmup 0.10;
- paged AdamW 8-bit, BF16, gradient checkpointing, `use_cache=False`, SDPA;
- log every 5 optimizer steps; checkpoint once per epoch, retain 3;
- ensure SHION Chat, Voice, image tools, browsers using CUDA, and other optional
  GPU workloads are stopped by the Owner before launch;
- stop on OOM, non-finite loss, sustained unexpected slowdown, or another process
  consuming GPU memory.

For 200 records, batch 1 and accumulation 8 yield 25 optimizer steps per epoch,
75 across three epochs, with 600 record forward/backward passes. Extrapolating
from this very small Gate suggests roughly 14–18 hours plus checkpoint overhead;
this is an estimate, not a benchmark. Physical peak should be expected near the
12,227 MiB limit, and no safe numeric margin can yet be promised.

A separate Owner decision should choose between accepting this single-GPU WDDM
risk, performing one bounded memory mitigation experiment, or using different
hardware/runtime placement. It must not trigger automatic Full Training or base
model replacement.

## Decision

All functional PASS conditions were met, but VRAM margin is too small for an
unqualified PASS.

**EXPERIMENT 0002 TRAINING FEASIBILITY: PASS WITH CAUTION**
