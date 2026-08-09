# SHION SFT Experiment 0001

This directory contains pre-training preparation only. It does not download a
base model or start training.

## Long-running execution policy

Codex prepares and validates commands, but the Owner runs Baseline, Full
Training, long Evaluation, large checkpoint comparisons, and long GGUF
conversion manually in PowerShell. Codex must not start such work and poll it.
After the Owner reports completion, Codex inspects the produced artifacts and
continues analysis. Short model-load checks and explicitly approved Smoke
Training remain eligible for Codex execution.

The source of truth remains `dataset/golden/`. Generated files under
`training/data/generated/` are disposable artifacts and must never be edited
back into Golden or the database.

## Owner-gated workflow

1. Review `reports/dataset_analysis.md` and `reports/training_architecture.md`.
2. Confirm the pinned official Mistral Model A revision and license.
3. Confirm GPU, VRAM, RAM, CUDA, Python, storage, and license acceptance.
4. Generate the derived records:

   `python training/scripts/convert_golden.py --golden-dir dataset/golden --output training/data/generated/shion_sft_exp_0001.jsonl --manifest training/data/generated/shion_sft_exp_0001.manifest.json`

5. The Owner manually runs the fixed evaluation against Model A.
6. Only after Owner approval, install/pin the training stack and run QLoRA.
7. Compare checkpoints after each epoch with the same evaluation and decoding.

The converter preserves every message string byte-for-byte after JSON decoding,
including newlines, `♪`, `♡`, `〜`, and `（笑）`. It does not render special
tokens. Training must use the selected tokenizer's `apply_chat_template` with
`add_generation_prompt=False`; the tokenizer supplies BOS/EOS and role tokens.
The optional canonical system prompt is inserted as a separate `system` message,
never concatenated with a user or assistant message.
