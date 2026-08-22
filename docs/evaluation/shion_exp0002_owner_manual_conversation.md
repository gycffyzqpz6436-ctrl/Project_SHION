# SHION Experiment 0002 — Owner Manual Conversation Evaluation

## Status and scope

This entry is **Owner Manual Evaluation**, not a production-model adoption decision.
It binds one server-side allowlisted alias to the completed Experiment 0002 adapter.
The browser cannot provide or replace the adapter path. The runtime is offline-only,
uses `trust_remote_code=False`, and fails model loading if either the base or adapter
does not match the recorded provenance.

## Immutable provenance

- Alias: `shion_gemma4_exp0002_manual`
- Display name: `SHION — Gemma 4 / Experiment 0002`
- Base: `google/gemma-4-12b-it`
- Base revision: `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`
- Base local path: `D:\AI\Project_SHION\models\experimental\gemma-4-12b-it`
- Adapter: `D:\AI\Project_SHION\training_output\shion_sft_exp_0002\full_training\run-20260822-221100\final_adapter`
- Manifest: `D:\AI\Project_SHION\training_output\shion_sft_exp_0002\full_training\run-20260822-221100\manifest.json`
- Dataset recorded by manifest: Golden 200
- Training: 3 epochs, LoRA `r=8`, `alpha=16`, `dropout=0.1`, 184 q/k/v/o targets

The runtime loads the Official Gemma checkpoint through the same
`Gemma4UnifiedForCausalLM` text-only architecture, `config.text_config`, and
checkpoint key mapping used by Experiment 0002 training/reload, then attaches the
adapter without merging it. The separate Official Gemma alias remains multimodal.
Missing, invalid, inactive, or mismatched adapters produce an explicit model-load
failure; the SHION alias never falls back to the Official base model.

## Owner startup

Open PowerShell and run:

```powershell
cd C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
training\.venv\Scripts\python.exe app\server.py --model shion_gemma4_exp0002_manual
```

Open `http://127.0.0.1:8765/`. Wait for `Ready`; while loading, sending is
disabled. Model Info must show `SHION`, `Gemma 4 12B IT`, Experiment `0002`,
Adapter `ACTIVE`, 184 targets, Golden 200, 3 epochs, and Owner Manual Evaluation.

All existing modes remain available. Start with **Neutral Conversation** for the
least confounded comparison. Minimal has no system prompt; Canonical uses the
existing canonical SHION prompt and has not been altered for this evaluation.

## Suggested manual checks

Use the same prompt first with `gemma4_12b_it_manual`, then with
`shion_gemma4_exp0002_manual`. Check:

- natural Japanese and casual conversation;
- appropriate use of the 「お兄さん」 address;
- SHION-like light teasing and kindness;
- assistant bias and persona retention during technical questions;
- excessive roleplay or invented context;
- apparent memorization of Golden text;
- repetition and foreign-language contamination.

Small starting set: `おはよ`, `今日仕事疲れた〜`, `ちょっと甘やかして`,
`今日何もしなかった`, `Windowsでポート3000使ってるプロセス確認したい`,
and `応用情報の勉強だるい`. Do not treat a successful runtime load as a
quality pass.

To switch models, wait until generation has stopped and use the allowlisted model
selector. Model switching retains the existing unload, GC/CUDA-cache cleanup, and
conversation-reset behavior. Stop the server with `Ctrl+C` in its PowerShell.

## Failure interpretation

- Missing `final_adapter`, manifest, config, or safetensors: load fails before GPU load.
- Manifest/base/revision/LoRA mismatch: load fails before GPU load.
- PEFT attach failure, inactive adapter, or target count other than 184: load fails;
  there is no base-only fallback.
- OOM: stop other GPU-heavy applications and restart. Do not change the fixed
  adapter path or enable network/custom code as a workaround.
