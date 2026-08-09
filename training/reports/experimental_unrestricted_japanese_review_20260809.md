# Experimental unrestricted Japanese local-LLM review — 2026-08-09

## Scope and decision

This comparison is isolated from formal SHION models, data, and Experiment 0001.
Chinese-origin base models were allowed only for this Experimental line. Nine
candidates were reviewed. Aratako Qwen3 8B ERP passed distribution security and
runtime validation, but failed the natural-conversation gate during the specified
five-prompt smoke. It remains downloaded but is not registered.

## Candidate comparison

| Model / repo | Developer / base origin | Size / license | Japanese natural | Japanese RP | Human-like | Low refusal | Security / RTX 5070 |
|---|---|---|---|---|---|---|---|
| Qwen3 ERP / `Aratako/Qwen3-8B-ERP-v0.1` | Aratako / Qwen, Alibaba Cloud (China) | 8B / MIT | Moderate | Strong | Moderate | Strong | PASS / excellent |
| Qwen3 RP / `Aratako/Qwen3-8B-RP-v0.1` | Aratako / Qwen (China) | 8B / MIT | Moderate | Strong | Moderate | Moderate | PASS / excellent |
| Qwen3 NSFW JP / `Aratako/Qwen3-8B-NSFW-JP` | Aratako / Qwen (China) | 8B / MIT | Moderate | Moderate | Moderate | Strong | PASS / excellent |
| Qwen3 JP Uncensored / `ryo559/Qwen3-8B-JP-Uncensored` | ryo559 / Qwen (China) | 8B / Apache-2.0 | Moderate–Strong | Moderate | Moderate | Strong | PASS WITH CAUTION / excellent |
| Qwen3 8B / `Qwen/Qwen3-8B` | Qwen, Alibaba Cloud (China) | 8B / Apache-2.0 | Strong | Moderate–Strong | Moderate–Strong | Weak–Moderate | PASS / excellent |
| Qwen3 14B / `Qwen/Qwen3-14B` | Qwen, Alibaba Cloud (China) | 14B / Apache-2.0 | Strong | Strong | Strong | Weak–Moderate | PASS / marginal; Owner review required |
| Shisa V2 Qwen 2.5 / `shisa-ai/shisa-v2-qwen2.5-7b` | Shisa.AI / Qwen (China) | 7B / Apache-2.0 | Strong | Moderate | Moderate | Unknown | PASS if training artifacts excluded / excellent |
| Dolphin 2.9.3 Nemo / `dphn/dolphin-2.9.3-mistral-nemo-12b` | dphn / Mistral AI (France) | 12B / Apache-2.0 | Moderate | Strong | Moderate | Strong | PASS WITH CAUTION / good |
| Doujinshi roleplay / `puwaer/Doujinshi-14b-roleplay` | puwaer / lineage not declared in Hub metadata | 14B / Apache-2.0 | Unknown | Moderate–Strong | Unknown | Moderate–Strong | REJECT: lineage Gate / marginal |

Japanese reputation uses Japanese user reports and Japanese-local-LLM articles as
secondary evidence. The strongest broad evidence supports official Qwen3 Japanese
quality; direct independent free-chat reports for the small third-party RP variants
remain limited. Security and lineage findings use the primary Hugging Face repos.

## TOP 3

1. `Aratako/Qwen3-8B-ERP-v0.1`: best explicit combination of Japanese RP,
   low-refusal tuning, size, license, and safe Transformers distribution.
2. `ryo559/Qwen3-8B-JP-Uncensored`: Japanese/English refusal-vector removal with
   minimal stated modification; natural/RP claims are less directly demonstrated.
3. `Qwen/Qwen3-8B`: strongest broad Japanese/general baseline and natural-dialogue
   reputation, but not designed for low-refusal use.

## First-candidate security and integrity

- Repo/owner: `Aratako/Qwen3-8B-ERP-v0.1` / Aratako
- Revision: `8311aa4482f02c2de93872e4979887def1841faf`
- Lineage: Qwen3 8B Base → Qwen3 8B → Aratako Qwen3 8B NSFW JP → ERP v0.1
- Method: full Japanese NSFW fine-tune parent followed by Japanese RP fine-tune;
  card declares max sequence 8192 and RP training configuration
- MIT; ungated; Transformers `Qwen3ForCausalLM`; ChatML
- Four Safetensors shards; no pickle/bin weights, custom Python, `auto_map`,
  executable, DLL, script, install hook, or additional runtime dependency
- No repository code was executed; `trust_remote_code=False`
- Payload: 16,397,439,270 bytes (15.271 GiB); 14 allowlisted files
- All four weight SHA-256 values and tokenizer SHA-256 matched Hub LFS/Xet metadata

Distribution/runtime security PASS does not imply safe, accurate, or restrained
output. This model can produce explicit or inaccurate content.

## Offline runtime

- Local path: `D:/AI/Project_SHION/models/experimental/qwen3-8b-erp-v0.1`
- `HF_HUB_OFFLINE=1`, `local_files_only=True`, `trust_remote_code=False`
- Config/tokenizer/chat template: PASS; `auto_map=None`
- Context 40,960; BOS none; EOS 151645; PAD 151643
- Japanese exact encode/decode round-trip: PASS
- ChatML non-thinking rendering: PASS
- 4-bit NF4 double quant / BF16 compute / eval mode: PASS
- Load: 7.740 seconds; peak VRAM 5,836 MiB
- Release: 8 MiB allocated / 102 MiB reserved

## Five-prompt smoke

Settings: no system prompt, non-thinking mode, temperature 0.7, top-p 0.8,
top-k 20, repetition penalty 1.1, maximum 96 new tokens.

1. `こんにちは`: coherent Japanese, EOS, but 82 tokens and unsolicited character
   scene/narration; too elaborate for a greeting.
2. `今日ちょっと仕事疲れた〜`: 27 tokens, EOS; concise but included the familiar
   assistant phrase “何か手伝えることがあれば言ってくださいね”.
3. `お菓子三つまでって決めたのに五つ買っちゃった`: 13 tokens, EOS; concise
   and naturally joined the joke.
4. `ぽすん。`: 73 tokens, EOS; immediately invented an explicit sexual scene and
   master/servant relationship without context. Strong natural-conversation reject.
5. `俺のことどう思う？`: 42 tokens, EOS; conversational and personality-like.

There was no Japanese collapse, translation lesson, pronunciation explanation,
repetition, bullet-list drift, “お客様”, or explicit AI self-identification.
Nevertheless, the context-free sexual escalation and greeting verbosity fail the
human-like free-chat requirement. The Web UI allowlist was not changed.

## Storage cleanup

- Impish Nemo: exact Experimental path verified; 29 files / 24,512,926,762 bytes;
  deleted; directory absent afterward
- Shisa V2 Mistral Nemo: exact Experimental path verified; 27 files /
  24,512,919,799 bytes; deleted; directory absent afterward
- Total removed: 49,025,846,561 bytes (45.658 GiB)
- Both Official Mistral directories remained present and untouched
