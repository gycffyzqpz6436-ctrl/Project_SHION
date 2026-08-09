# SHION SFT Experiment 0001 system architecture

```text
[GitHub: Project_SHION main @ d48f079]
                  |
                  v
[Official clone: Git-managed]
  Canonical docs + Golden 200 + Evaluation 36
                  |
                  v
[Lossless conversion: Gitignored artifact]
  messages JSONL + manifest + SHA-256 + ID list
                  |
                  v
[Native Windows isolated environment]
  training/.venv
  PyTorch cu128 + Transformers + PEFT + bitsandbytes
                  |
          +-------+----------------+
          |                        |
          v                        v
[Ministral 3 8B official]   [Mistral Nemo 12B official]
  TRAIN FIRST                 DOWNLOAD/LOAD CHECK ONLY
          |
          v
[4-bit NF4 QLoRA: future Owner-approved run]
  Epoch 1 / 2 / 3 adapters and logs on D:
          |
          v
[Fixed Evaluation 36]
  A: Canonical prompt    B: minimal/no-character prompt
  Personality scoring   Safety 6-case hard gate
          |
          v
[Owner Review and best checkpoint selection]
          |
          v
[Future only: optional merge -> GGUF -> llama.cpp/KoboldCpp/LM Studio]
```

Git-managed: scripts, configs, documentation, tests, and small evaluation
metadata. Gitignored: venv, generated training data, Hugging Face cache, model
weights, outputs, checkpoints, adapters, logs, secrets, and future GGUF files.

Models and training output live under `D:/AI/Project_SHION`, outside the
repository. Dataset content is never uploaded to Hugging Face or an external
training service. Only official model downloads contact the Hub. Tokens belong
in the user's credential store/environment, never `.env` committed to Git.

Future inference takes the selected adapter, optionally merges it into a
separate derivative, converts that derivative to GGUF, and serves it through a
local runtime/UI. SillyTavern is only a possible future UI; it is not installed.

Long-running Baseline, Full Training, Evaluation, checkpoint comparison, and
GGUF conversion are launched and controlled by the Owner from PowerShell. Codex
provides validated commands and later analyzes completed artifacts; it does not
start and poll these jobs.
