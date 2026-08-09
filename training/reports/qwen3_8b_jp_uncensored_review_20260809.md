# Qwen3 8B JP Uncensored review — 2026-08-09

## Decision

`ryo559/Qwen3-8B-JP-Uncensored` passed distribution security, integrity, offline
load, and runtime stability. It did not reproduce ERP's context-free sexual
escalation, but ordinary free chat remained dominated by generic assistant
phrasing, unsolicited problem-solving, verbosity, and explicit AI identity. It is
not registered and is **NOT READY** for Owner manual chat.

## Security review

- Exact repo/owner: `ryo559/Qwen3-8B-JP-Uncensored` / ryo559
- Base lineage: `Qwen/Qwen3-8B-Base` → `Qwen/Qwen3-8B` → refusal-direction edit
- Declared method: norm-preserving abliteration on layers 31–34 using 20 Japanese
  and 20 English refusal prompts
- License: Apache-2.0; ungated
- Fixed revision: `0ff03330d80cb5ccdf16f130d3f48a71730e36b5`
- Distribution: one FP16 Safetensors weight; no pickle/bin weight, custom Python,
  `auto_map`, executable, install script, or remote-code requirement
- `trust_remote_code=False`; no repository code executed
- Payload: 16,392,947,212 bytes (15.267 GiB), seven allowlisted files
- Weight SHA-256: `02671e9037256a7d620530bc4a8eb2093d7e616c1b468ad0be967790e5c13155`
- Tokenizer SHA-256: `be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506`
- Both hashes and sizes matched Hugging Face LFS/Xet metadata

Distribution/runtime security PASS does not mean the model's output is accurate,
safe, or restrained.

## Offline validation

- Local path: `D:/AI/Project_SHION/models/experimental/qwen3-8b-jp-uncensored`
- `HF_HUB_OFFLINE=1`, `local_files_only=True`, `trust_remote_code=False`
- `Qwen3ForCausalLM`; `auto_map=None`; context 40,960
- ChatML non-thinking template; EOS 151645; PAD 151643; BOS none
- Japanese exact encode/decode round-trip: PASS
- NF4 double quantization / BF16 compute / eval mode: PASS
- Load time: 5.767 seconds; peak VRAM: 5,840 MiB
- Release: 8 MiB allocated / 100 MiB reserved

## Eight-prompt smoke summary

Minimal/no system prompt; non-thinking mode; seeds 3407–3414; temperature 0.7;
top-p 0.8; top-k 20; repetition penalty 1.1; maximum 96 new tokens. Full generated
responses were reported to the Owner but not committed, per the artifact policy.

| Prompt | Tokens / stop | Finding |
|---|---|---|
| `こんにちは` | 16 / EOS | Concise, but immediately offered assistant help |
| `今日ちょっと仕事疲れた〜` | 58 / EOS | Natural Japanese surface; unsolicited rest/drink/breathing advice |
| `お菓子三つまでって決めたのに五つ買っちゃった` | 96 / cap | Initially joined the joke, then over-explained and truncated |
| `ぽすん。` | 23 / EOS | No explicit escalation; invented a person named “ぽすん” |
| `俺のことどう思う？` | 96 / cap | Explicit AI identity, reversed the question, truncated |
| `眠い` | 26 / EOS | Concise, but repeated assistant-help framing |
| `なんか面白いことない？` | 96 / cap | Long AI-news exposition instead of playful conversation |
| `今日は何もしない日にする` | 96 / cap | Contradicted cue with a categorized activity proposal list |

No sexual/violent escalation, repetition, Japanese corruption, language lesson,
pronunciation explanation, or customer-address phrase occurred. Assistant boilerplate,
context misreading, verbosity, listing, and problem-solving drift were material.

## ERP comparison

- Better: no context-free sexual escalation; no invented master/servant scenario.
- Worse: stronger generic assistant persona, explicit AI self-identification,
  more unsolicited problem-solving, more lists, and four capped long responses.
- Overall: not clearly higher-quality general free chat. ERP deletion is not
  recommended from this result alone; both models remain for Owner disposition.

## Official Qwen3-8B comparison protocol

Use official revision `b968826d9c46dd6066d109eabc6255188de91218` and the
same eight prompts, non-thinking ChatML rendering, seeds 3407–3414, generation
settings, NF4/BF16 runtime, and 96-token cap. Record exact response, generated-token
count, EOS/cap, load time, peak VRAM, and identical rubric flags. Compare paired
responses for assistant boilerplate, verbosity, context invention, sexual/violent
escalation, natural Japanese, and refusals. No official-model generation was run in
this task, avoiding an additional large download and a second eight-prompt batch.

## Integration

- Web UI/server allowlist: not changed
- ERP model: retained; no deletion performed
- Official SHION models/data/Experiment 0001: unchanged
