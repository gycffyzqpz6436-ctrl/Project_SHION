# Owner-gated execution commands

Run from the repository root with the venv Python. Baseline and Full Training
are Owner-manual commands; Codex does not start or poll them.

Smoke training (four records, two optimizer steps):

```powershell
training\.venv\Scripts\python.exe training\scripts\train_sft.py --common training\configs\common.yaml --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml --smoke --owner-approved-training
```

Baseline mode A, Canonical System Prompt:

```powershell
training\.venv\Scripts\python.exe training\scripts\run_baseline.py --common training\configs\common.yaml --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml --mode canonical --owner-approved-baseline
```

Baseline mode B, no character System Prompt:

```powershell
training\.venv\Scripts\python.exe training\scripts\run_baseline.py --common training\configs\common.yaml --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml --mode minimal --owner-approved-baseline
```

Full three-epoch training, only after smoke review:

```powershell
training\.venv\Scripts\python.exe training\scripts\train_sft.py --common training\configs\common.yaml --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml --owner-approved-training
```

Each command requires an explicit approval flag so accidental invocation without
Owner intent exits before model load or output creation.

## Experiment 0002 — Owner-Manual Launch Gate

This is the required gate before any Gemma 4 Full Training. Codex does not run
or poll this command. Run every command from:

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
```

### 1. Before starting

1. Stop SHION Web Chat with `Ctrl+C` in its own console. If Voice was started
   separately, stop it in its own console too.
2. Stop Stable Diffusion, games, and other GPU-heavy applications normally.
   The Launch script never kills another process.
3. Check disk and GPU:

```powershell
Get-PSDrive D | Select-Object Used, Free
nvidia-smi
```

The script refuses Launch below 5 GiB free, Full Training below 20 GiB free,
GPU use above 1,536 MiB, GPU free memory below 10,240 MiB, a non-RTX-5070 GPU,
or unavailable CUDA. Existing checkpoints are never deleted.

For overnight Full Training, connect AC power, confirm cooling, disable or
extend sleep manually, pause automatic Windows Update restart, and keep GPU-heavy
applications closed. This Runbook does not change Windows settings.

### 2. Monitoring PowerShell

Open a separate PowerShell and leave one of these running:

```powershell
nvidia-smi -l 2
```

More compact telemetry:

```powershell
nvidia-smi --query-gpu=timestamp,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw --format=csv -l 2
```

### 3. CPU/static validation

This command never loads the model:

```powershell
training\.venv\Scripts\python.exe -m training.scripts.run_exp0002_manual validate --config training\configs\shion_sft_exp_0002_gemma4.yaml
```

### 4. Launch Gate — exactly five optimizer steps

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
training\.venv\Scripts\python.exe -m training.scripts.run_exp0002_manual launch --config training\configs\shion_sft_exp_0002_gemma4.yaml
```

`launch` has no user-configurable step argument. It is hard-capped at five
optimizer steps and cannot continue into Full Training. With gradient
accumulation 8 it processes 40 record passes, then saves only the adapter and
stops. Each step prints loss, pre-optimizer gradient norm, learning rate, and
elapsed time. Metrics also contain Torch allocated/reserved/peak plus non-fatal
NVIDIA monitoring results.

Artifacts are created in a timestamped directory under:

```text
D:\AI\Project_SHION\training_output\shion_sft_exp_0002\launch_gate\
```

Each run contains `adapter/`, `metrics.json`, and `manifest.json`. It contains
no raw Dataset text. The Base Model is never saved.

### 5. Review and reload

Find the newest manifest and inspect the compact result:

```powershell
$manifest = (Get-ChildItem 'D:\AI\Project_SHION\training_output\shion_sft_exp_0002\launch_gate' -Filter manifest.json -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
Get-Content $manifest -Raw
Get-Content (Join-Path (Split-Path $manifest) 'metrics.json') -Raw
```

Then perform the separate offline GPU reload validation:

```powershell
training\.venv\Scripts\python.exe -m training.scripts.run_exp0002_manual reload --manifest $manifest
```

Success candidate:

- exactly 5/5 steps and manifest/metrics status `PASS`;
- finite losses and gradient norms without accelerating growth;
- no OOM/CUDA error and no monitoring warning that hides VRAM state;
- physical headroom remains materially above the prior unsafe range;
- temperature is normal for this PC;
- adapter save and manual reload both pass.

Owner NO-GO/review candidate:

- loss or gradient NaN/Inf;
- gradient norm accelerates sharply across steps (do not reject one merely large
  finite value by a fixed threshold);
- OOM, CUDA error, headroom collapse, WDDM spill recurrence, abnormal
  temperature, or adapter save/reload failure.

Send Codex/ChatGPT only the final console summary, five loss/grad-norm lines,
peak VRAM, temperature, runtime, reload result, and warnings/errors. The full log
or private Dataset text is unnecessary.

### 6. Full Training — separate Owner approval only

Do **not** confuse this with the Launch command. Use it only after reviewing the
Launch Artifact and explicitly approving Full Training:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
training\.venv\Scripts\python.exe -m training.scripts.run_exp0002_manual full --config training\configs\shion_sft_exp_0002_gemma4.yaml --owner-approved-full-training
```

Without `--owner-approved-full-training`, the command refuses before model load
or output creation. The candidate run is three epochs, 25 optimizer steps per
epoch, 75 total, with one checkpoint per epoch and at most three checkpoints.

Trainer checkpoint resume is available. Resume only the exact `checkpoint-*`
directory from the same run; the CLI verifies its parent manifest mode, config
hash, and Dataset hash before model load:

```powershell
training\.venv\Scripts\python.exe -m training.scripts.run_exp0002_manual full --config training\configs\shion_sft_exp_0002_gemma4.yaml --resume-from-checkpoint 'D:\AI\Project_SHION\training_output\shion_sft_exp_0002\full_training\run-YYYYMMDD-HHMMSS\checkpoint-25' --owner-approved-full-training
```

Based on the bounded precision run, Launch is estimated at roughly 2–6 minutes
including load and initialization. Full Training is provisionally 15–40 minutes
including three adapter/checkpoint saves. These are extrapolations, not a GPU
measurement of this Trainer/paged-optimizer path; replace them with Launch Gate
throughput before scheduling Full Training.

Baseline never overwrites a completed JSONL or manifest. An interrupted run
keeps `*.jsonl.partial`; after inspecting it, add `--resume` to the same command.
Resume validates that the existing rows form the exact prefix of the fixed
evaluation before loading the model. Completion atomically promotes the partial
JSONL and its manifest.

During Owner-manual runs, watch `nvidia-smi`, progress lines `[NN/36]`, OOM or
CUDA errors, temperature/power, and the growing `.partial` file. Baseline uses
inference only and cannot modify the official model weights.

## Owner-manual free chat

Minimal base-model chat:

```powershell
training\.venv\Scripts\python.exe training\scripts\chat_local.py --common training\configs\common.yaml --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml --mode minimal
```

Canonical-prompt base-model chat changes only `--mode minimal` to
`--mode canonical`. Add `--adapter <existing-adapter-directory>` for a future
LoRA comparison. Session logging is off by default; `--save-session <new-path>`
creates UTF-8 JSONL and refuses to overwrite an existing file. The CLI warns
near the model context limit and rejects a turn that would exceed it; use
`/reset` to clear history without reloading the model.
