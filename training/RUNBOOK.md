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
