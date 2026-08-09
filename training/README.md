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

## Local interactive chat

`scripts/chat_local.py` provides text-only, multi-turn conversation with the
pinned local Model A. It loads the model once in 4-bit NF4/BF16 inference mode,
never loads Golden data, and does not write a session unless `--save-session`
is explicitly supplied. Modes `minimal` and `canonical` use the same prompt
selection code as evaluation. `/status`, `/history`, `/reset`, `/help`, and
`/exit` are available. Vision input is unsupported.

An optional existing PEFT LoRA directory may be supplied with `--adapter` for
future base/fine-tuned comparisons. The CLI only loads it for inference and
never creates or updates an adapter or base-model weights.

## Local web chat MVP

Run `training\.venv\Scripts\python.exe app\server.py` from the repository
root, then open `http://127.0.0.1:8765`. The responsive HTML/CSS/JavaScript UI
and JSON API are entirely local and use no CDN, telemetry, cloud model, or
Hugging Face communication. The server binds only to `127.0.0.1`; LAN,
Tailscale, Internet exposure, and port forwarding are intentionally disabled.

The model loads once in the background. Browser history is held only in server
memory and `/api/reset` clears it; nothing is persisted to disk. The UI offers
minimal, neutral-conversation, and canonical modes. Neutral mode uses the
non-character prompt in `app/prompts/neutral_conversation.txt`; canonical mode
is unchanged. A future existing LoRA may be selected only at server startup
with `--adapter`; the browser cannot supply model paths.

Future smartphone/tablet access is Stage 2/3 work and requires a separate
design for authentication, TLS, and firewall policy before enabling a LAN or
Tailscale bind. Do not change the current loopback restriction to expose it.

The Web UI model selector is backed by `app/model_registry.json`; clients send
an alias, never a path. Switching is allowed only while generation is idle,
releases the current model, clears all conversation history, empties CUDA
cache, and then loads the selected model. Third-party entries carry an explicit
badge. Lumimaid Magnum remains visible but disabled because its repository does
not declare a license.

The default remains `ministral3_official`. To start directly with the Owner
Manual Test JP-Uncensored model, the Owner may run:

```powershell
training\.venv\Scripts\python.exe app\server.py --model qwen3_8b_jp_uncensored_manual

# Gemma 4 official 12B comparison candidate (run only after runtime gate is marked available)
training\.venv\Scripts\python.exe app\server.py --model gemma4_12b_it_manual
```

Available aliases are `ministral3_official`, `nemo12b_official`,
`qwen3_8b_jp_uncensored_manual`, `qwen3_8b_erp_manual`, and
`gemma4_12b_it_manual`. These entries are
explicitly Experimental / Third-party / Owner Manual Test; availability does
not mean Quality Gate approval or formal SHION adoption. They use fixed
non-thinking generation settings. Gemma 4 is the official Apache-2.0 checkpoint
selected for Japanese-base Owner comparison; it is not an approved SHION base.
`lumimaid12b_experimental` is metadata-only
and is rejected by the server even if a client submits the alias directly.

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
