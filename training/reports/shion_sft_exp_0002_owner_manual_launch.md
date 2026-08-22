# SHION SFT / QLoRA Experiment 0002 — Owner-Manual Launch Gate

Status: **READY FOR OWNER MANUAL EXECUTION — NOT EXECUTED BY CODEX**

Prepared: 2026-08-22

The production candidate is fixed in
`training/configs/shion_sft_exp_0002_gemma4.yaml`. Launch and Full Training share
the same official Gemma 4 text-only NF4/double-quant/BF16 path, precision-aware
Gemma norm FP32 and tied embedding/lm-head BF16 policy, 184-target r8 LoRA,
assistant-only Dataset processing, paged AdamW 8-bit optimizer, cosine schedule,
gradient accumulation 8, max length 512, and non-reentrant gradient
checkpointing. Launch differs only by `max_steps=5` and final Launch artifact
placement; it does not run evaluation or an epoch checkpoint schedule.

The earlier Preparation memo's 1,024-token initial candidate is superseded by
the bounded 512-token zero-truncation evidence. The Precision Gate used
`torch.optim.AdamW` for controlled attribution, whereas the existing production
candidate specifies `paged_adamw_8bit`. Therefore the manual Launch Gate is also
the first runtime validation of the final optimizer candidate; any optimizer
error or materially different memory behavior is an Owner NO-GO.

Safety is enforced before model load:

- exact model/revision/config/Dataset SHA and 200 unique records;
- immutable five-step Launch constant and config guard;
- separate Full Training subcommand and mandatory approval flag;
- at least 5 GiB free for Launch or 20 GiB for Full Training;
- RTX 5070, CUDA, at most 1,536 MiB pre-existing use and at least 10,240 MiB free;
- offline Hub mode, local-only loading and `trust_remote_code=False`;
- timestamped non-overwriting output directories.

At runtime, non-finite loss, gradient, or gradient norm aborts the run. CUDA/OOM
exceptions are recorded as failures. NVIDIA telemetry failure is recorded as a
monitoring warning without being confused with training failure. The compact
JSON artifacts contain numeric/config metadata and no raw private Dataset text.

The manifest records schema/status/mode, exact model ID/revision/local path and
class, config and Dataset hashes, record count, precision/quantization/LoRA and
training settings, five-step limit, disk/GPU preflight, output/metrics/adapter
paths, adapter files, completed steps, timestamps, and checkpoints. The adapter
is saved separately; the Base is never saved.

Full resume uses Transformers Trainer checkpoint state. It is accepted only for
an existing `checkpoint-*` directory whose parent manifest is a Full run and
whose config and Dataset hashes still match. This is safer than deleting or
rewriting checkpoints, but resume remains Owner-manual.

No model load, CUDA initialization, forward/backward, optimizer step,
generation, Launch Gate, adapter reload, or Full Training was performed while
preparing this flow. Only CPU/static validation and tests were run.
