# Pre-training validation — 2026-08-09 JST

## Passed

- Repository `main` equals `origin/main` at `d48f079`; `git fetch` performed
  without altering Owner-review work.
- Golden and database tracked files are unchanged.
- Golden conversion produced 200 records from only Owner-approved Golden IDs.
- Converted messages exactly preserve multi-turn content and Unicode.
- Maximum rendered length is 835 tokens under the selected Model A tokenizer;
  configured limit is 2048 and no truncation is needed.
- Exact assistant-only masks exist for all 200 records; 26,470 assistant tokens
  are trainable and no sample has an empty mask.
- Fixed evaluation: 36 unique prompts; Safety has six hard-gate cases; no exact
  Golden prompt overlap.
- PyTorch sees RTX 5070 `sm_120`; BF16 passed.
- bitsandbytes NF4 CUDA quantize/dequantize passed.
- Model A and B config/tokenizer/chat-template checks passed with
  `local_files_only` and `trust_remote_code=False`.
- Model A 4-bit load passed at 5,924 MiB peak.
- Model B 4-bit load passed at 8,099 MiB peak.
- PEFT LoRA injection passed: 272 language-attention targets, zero vision
  targets, 7,241,728 trainable parameters.
- Python compile, YAML parse, config gates, Dataset Validator, and tests passed:
  18 tests plus 10 subtests.
- Training and baseline entry points refuse execution without explicit Owner
  approval flags.
- `.gitignore` covers venv, generated data, outputs, model formats, `.env`, and
  logs. No model-weight or secret-like file is tracked.
- `git diff --check` passed. The only message is Git's Windows line-ending
  advisory for `.gitignore`.

## Not run by design

- forward/backward
- smoke training
- checkpoint save/reload
- baseline 36 generation
- LoRA training
- adapter inference
- Nemo training

These require the next Owner approval stage.

## Planning estimates

- Model A training VRAM: approximately 8.5–11.5 GiB at batch 1 and max 2048;
  smoke measurement is the authority.
- Full three-epoch runtime: roughly 1–3 hours on this RTX 5070 for 200 short
  records, but Windows/SDPA/checkpointing throughput is not yet measured.
- Current model payload: 39.484 GiB total.
- D: free after downloads: 209.55 GB decimal (~195.16 GiB).
- Reserve another 20–40 GB for adapters, optimizer/checkpoints, evaluation,
  caches, and optional future conversion. Current free space is sufficient.

## Remaining gate

The environment is ready for the two-step execution sequence: Owner-approved
smoke training, review of peak VRAM/save/reload/inference, then separately
Owner-approved baseline and full training. It is not evidence that the unrun
forward/backward path will fit; that is exactly what the smoke gate tests.

