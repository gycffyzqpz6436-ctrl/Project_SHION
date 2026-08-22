# SHION SFT / QLoRA Experiment 0002 — Precision-Aware k-bit Preparation Gate

Status: **PASS WITH CAUTION — FULL TRAINING RECOMMENDATION GO, OWNER APPROVAL REQUIRED**

Executed: 2026-08-22

## Scope

The Gate compared PEFT 0.20.0's current preparation with a Project SHION
precision-aware helper. Both used the unchanged local
`google/gemma-4-12b-it` revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`, official
`Gemma4UnifiedForCausalLM`, NF4 double quantization, BF16 compute, seed 42,
LoRA r8 / alpha 16 / dropout 0.10 on the same 184 q/k/v/o targets, AdamW
5e-5, batch size 1, max length 512, assistant-only loss, non-reentrant gradient
checkpointing, and the unchanged 200-record Dataset. Each path ran one longest
record step and the fixed four-record/two-step smoke only. Full Training was not
executed.

## PEFT 0.20.0 source audit

The installed implementation is
`peft/utils/other.py::prepare_model_for_kbit_training`. It:

1. freezes every base parameter;
2. for non-GPTQ/AQLM/EETQ/HQQ/TorchAO paths, casts every BF16/FP16 parameter
   whose class is not `Params4bit` to FP32;
3. clears the CUDA cache after the bulk cast;
4. enables gradient checkpointing for a k-bit model;
5. only installs an input-requires-grad hook for reentrant checkpointing.

The code does not classify LayerNorm, embeddings, or lm-head separately. Its
docstring describes norm and lm-head upcasting, but its actual predicate applies
to every non-`Params4bit` BF16/FP16 parameter.

Gemma's actual pre-preparation inventory was:

| Category | Tensors | Elements | BF16 bytes |
|---|---:|---:|---:|
| Tied input embedding/lm-head storage | 1 | 1,006,632,960 | 2,013,265,920 |
| Norm parameters | 289 | 769,792 | 1,539,584 |
| Total non-4-bit | 290 | 1,007,402,752 | 2,014,805,504 (1,921.47 MiB) |

The 328 packed `Params4bit` tensors used 5,449,973,760 uint8 storage bytes and
were correctly excluded. There were no separate non-quantized attention or MLP
parameters outside the norm category.

Current PEFT converted all 290 tensors to FP32: embedding 4,026,531,840 bytes
and norms 3,079,168 bytes, total 4,029,611,008 bytes. The storage increase was
exactly 2,014,805,504 bytes (1,921.47 MiB). It also broke runtime storage-pointer
sharing between the input embedding and lm-head by casting their two Parameter
views independently, although the model's configured tied-weight semantics
remained declared.

## Precision-aware policy

The auditable Project helper:

- accepts only a 4-bit-loaded `Gemma4UnifiedForCausalLM`;
- sets `use_cache=False`;
- freezes every base parameter;
- keeps all 289 Gemma norm parameters FP32;
- keeps the tied input embedding/lm-head storage BF16;
- requires non-reentrant gradient checkpointing and enables it explicitly;
- leaves every `Params4bit` tensor untouched.

It does not modify PEFT, Transformers, site-packages, the checkpoint, or saved
base weights. LoRA is attached afterward and remains FP32. The official
`tie_word_embeddings=True` and `_tied_weights_keys = {lm_head.weight:
model.embed_tokens.weight}` semantics were verified. The input/output data
pointers remained identical after preparation, LoRA attachment, and adapter
reload.

## Static and training comparison

| Metric | Current PEFT | Precision-aware | Difference |
|---|---:|---:|---:|
| Base allocated | 7,284.69 MiB | 7,284.69 MiB | 0 |
| Post-preparation allocated | 9,206.16 MiB | 7,286.16 MiB | **-1,920.00 MiB** |
| LoRA attached allocated | 9,246.84 MiB | 7,326.84 MiB | **-1,920.00 MiB** |
| BF16 parameter bytes after preparation | 0 | 2,013,265,920 | +2,013,265,920 |
| FP32 parameter bytes after preparation | 4,029,611,008 | 3,079,168 | -4,026,531,840 |
| Longest peak allocated | 10,921.38 MiB | 8,607.72 MiB | -2,313.65 MiB |
| Longest peak reserved | 11,372 MiB | 9,036 MiB | -2,336 MiB |
| Smoke peak allocated | 11,051.56 MiB | 8,736.35 MiB | -2,315.21 MiB |
| Smoke peak reserved | 11,956 MiB | 9,332 MiB | -2,624 MiB |
| NVIDIA physical peak | 11,874 MiB | **9,991 MiB** | **-1,883 MiB** |
| Physical margin (12,227 MiB total) | 353 MiB | **2,236 MiB** | +1,883 MiB |
| WDDM allocation beyond physical capacity | Prior recurring risk | Not observed | Clearly reduced in bounded run |
| Longest runtime | 1.486 s | 1.627 s | +0.141 s / +9.5% |
| Two-step runtime | 3.936 s | 3.264 s | -0.672 s / -17.1% |
| Longest loss | 4.669636 | 4.656247 | -0.013390 / -0.29% |

The runtime differences are too small and WDDM-sensitive to claim a speed
change. The memory reduction is large, direct, and consistent with the audited
dtype change.

Control smoke losses were 5.892049 and 5.295005. Precision-aware losses were
5.969169 and 5.465226. All logits, losses, and gradients were finite. All 368
LoRA gradient tensors existed; frozen base gradients were absent. Longest-record
global gradient norm changed from 4.67759 to 9.33607. This is not an explosion
and optimization remained stable, but the roughly twofold change is the main
reason for the caution qualifier and should be monitored during Full Training.

## Adapter and compatibility

The precision-aware smoke adapter was saved outside Git as Safetensors under:

`D:/AI/Project_SHION/training_output/shion_sft_exp_0002/precision_gate/precision/adapter`

Offline reload against the unchanged text-only base passed with zero missing
keys, 184 active targets, FP32 adapter weights, correct local base reference, and
preserved tied embedding/lm-head pointer sharing.

Risks and controls:

- Norms remain FP32, reducing the principal numerical-stability risk.
- The frozen tied embedding/lm-head remains BF16. The small loss difference and
  larger gradient norm demonstrate that this is not bitwise equivalent to the
  FP32 control, even though the bounded Gate is stable.
- Adapter serialization and inference loading are compatible; no merged model
  was created. Future merge workflows must still be separately verified.
- This helper intentionally mirrors PEFT 0.20.0 behavior. Every PEFT or Gemma
  architecture upgrade requires a fresh source and dtype audit.

The minimum one-GiB reduction target and preferred 1.5–2 GiB headroom target
were both exceeded. WDDM oversubscription was not observed in the bounded
precision run. The result supports a Full Training GO recommendation, but only
after explicit Owner approval and with early-step gradient/loss/VRAM monitoring.

**EXPERIMENT 0002 PRECISION GATE: PASS WITH CAUTION**

**FULL TRAINING RECOMMENDATION: GO**
