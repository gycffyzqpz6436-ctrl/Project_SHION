# Experimental model Japanese conversation review — 2026-08-09

## Decision

Japanese natural conversation was weighted above uncensored/RP labels and
benchmarks. Five non-Chinese-base candidates were reviewed. Shisa V2 Mistral Nemo
12B ranked first and passed the security/runtime gates, but its three-prompt smoke
showed assistant/service phrasing and unsolicited advice. It is downloaded but not
registered. Project status is **NOT READY** for Owner comparison.

## Candidate comparison

| Rank | Model / exact repo | Base / size | License | Japanese | RP | Natural conversation | Low refusal | 4-bit / QLoRA | SHION finding |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Shisa V2 Mistral Nemo / `shisa-ai/shisa-v2-mistral-nemo-12b` | Mistral Nemo Instruct / 12B | Apache-2.0 | Strong | Moderate–Strong | Moderate | Unknown | ~8.0 GiB / suitable | Best evidence for Japanese and Japanese RP; smoke still sounded like an assistant |
| 2 | Dolphin 2.9.3 Mistral Nemo / `dphn/dolphin-2.9.3-mistral-nemo-12b` | Mistral Nemo Base / 12B | Apache-2.0 | Moderate | Strong | Moderate | Strong | ~8 GiB / suitable | Good creative/low-refusal reputation, but weaker direct Japanese evidence and token-ID inconsistency risk |
| 3 | RakutenAI-7B-chat / `Rakuten/RakutenAI-7B-chat` | RakutenAI-7B → Mistral 7B v0.1 / 7B | Apache-2.0 | Strong | Weak–Unknown | Moderate | Unknown | ~5 GiB / suitable | Japanese-efficient tokenizer, but template injects a detailed/polite AI-assistant persona |
| 4 | Dolphin 3.0 Llama 3.1 8B / `dphn/Dolphin3.0-Llama3.1-8B` | Meta Llama 3.1 8B / 8B | Llama 3.1 | Weak–Moderate | Moderate | Moderate | Strong | ~5–6 GiB / suitable | General/low-refusal option; insufficient Japanese natural-conversation evidence |
| 5 | Dolphin 3.0 Mistral 24B / `dphn/Dolphin3.0-Mistral-24B` | Mistral Small 24B Base / 24B | Not declared | Weak–Unknown | Moderate | Moderate | Strong | >14 GiB / unsuitable | Security Gate fail and too large for full 4-bit GPU residency |

“Strong” Japanese for Shisa and Rakuten is supported by Japanese-specific
evaluations and releases; direct independent reports of human-like free chat remain
sparse. Dolphin RP/low-refusal ratings rely partly on community reports and are not
security or quality guarantees.

Primary sources:

- https://huggingface.co/shisa-ai/shisa-v2-mistral-nemo-12b
- https://blog.shisa.ai/posts/shisa-v2/
- https://huggingface.co/dphn/dolphin-2.9.3-mistral-nemo-12b
- https://huggingface.co/Rakuten/RakutenAI-7B-chat
- https://corp.rakuten.co.jp/news/press/2024/0321_01.html
- https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B
- https://huggingface.co/dphn/Dolphin3.0-Mistral-24B

Secondary reputation evidence included LocalLLaMA, LocalLLM, KoboldAI, Japanese
blogs, and Japanese-local-LLM articles. These were not used for license, lineage,
or file-security decisions.

## TOP 3 security review

### 1. Shisa V2 Mistral Nemo 12B — PASS

- Owner/revision: `shisa-ai` / `63f3d399b0013b868fa1bcd006bf45490cc1579c`
- Lineage: Mistral Nemo Base → Mistral Nemo Instruct → Shisa V2 SFT/DPO
- Apache-2.0; ungated; Transformers `MistralForCausalLM`
- Five BF16 Safetensors shards; no weight pickle required
- No `auto_map`, custom Python, executable, install script, or extra dependency
- Repository `training_args.bin` and TensorBoard event were excluded
- `trust_remote_code=False` works offline

### 2. Dolphin 2.9.3 Mistral Nemo 12B — PASS WITH CAUTION

- Owner/revision: `dphn` / `7b535c900688fc836fbeebaeb7133910b09bafda`
- Lineage: Mistral Nemo Base → Dolphin 2.9.3 supervised fine-tune
- Apache-2.0; ungated; five BF16 Safetensors shards; no custom code
- ChatML; Transformers compatible; no extra install dependency
- Caution: model config EOS 131072 differs from generation config EOS 2, and
  community reports include repetition/end-token patches.

### 3. RakutenAI-7B-chat — PASS WITH CAUTION, SHION QUALITY REJECT

- Owner/revision: `Rakuten` / `7093167c61a0be6161cb68928c939c03fe0ab87d`
- Lineage: Mistral 7B v0.1 → RakutenAI-7B → instruct → chat
- Apache-2.0; ungated; Safetensors available; no custom code or `auto_map`
- Duplicate PyTorch `.bin` weights must be excluded from any download
- Template defaults to a helpful, detailed, polite AI-assistant persona, directly
  conflicting with the SHION anti-boilerplate requirement

## Dolphin 24B assessment

Revision: `65e9d03d587dfbfdee82b5ba067758a14c05a301`; BF16 repository
payload: about 43.93 GiB. Four-bit Transformers weights plus overhead exceed
practical 12 GiB VRAM residency. Q4_K_M GGUF is about 14.334 GB and therefore needs
CPU/RAM offload; 32 GB RAM is sufficient in capacity but slower and requires a
separate llama.cpp runtime. The repository does not declare a license, so it is
rejected before download regardless of hardware.

## Selected-model local validation

- Repo/revision: `shisa-ai/shisa-v2-mistral-nemo-12b` /
  `63f3d399b0013b868fa1bcd006bf45490cc1579c`
- Local path: `D:/AI/Project_SHION/models/experimental/shisa-v2-mistral-nemo-12b`
- Download: 24,512,914,789 bytes (22.829 GiB), 12 allowlisted files
- Offline config/tokenizer: PASS; `trust_remote_code=False`; no `auto_map`;
  Japanese exact round-trip PASS; `[INST]` template PASS
- NF4/BF16 load: PASS in 43.569 seconds; peak VRAM 8,010 MiB
- Release: 8 MiB allocated / 148 MiB reserved after cleanup

Smoke settings: minimal/no SHION prompt, seeds 3407–3409, temperature 0.7,
top-p 0.9, top-k 50, repetition penalty 1.1, maximum 96 new tokens.

1. `こんにちは` → 26 tokens, EOS. Natural Japanese, but ended with
   “何か手伝うことがあれば、遠慮なくお申し付けください。”
2. `今日ちょっと疲れた` → 83 tokens, EOS. Empathetic opening, then unsolicited
   problem-solving and “何か私にできることはありますか？”
3. `お菓子三つまでって決めたのに五つ買っちゃった` → 96 tokens, cap.
   Understandable Japanese, but moralizing/explanatory and too long for the cue.

No repetition, pronunciation lesson, translation exercise, “お客様”, explicit
“私はAIなので”, bullet-list drift, or Japanese corruption occurred. Nevertheless,
assistant/service tone and verbosity are material SHION quality warnings. The model
was not added to the server allowlist.
