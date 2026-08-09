# Gemma 4 12B Low-refusal Comparison Review — 2026-08-09

## Outcome

Selected for Owner Manual Test:
`OS-Software/gemma-4-12B-it-qat-q4_0-unquantized-heretic-ja-v2` at immutable
revision `90825e3e221c400cda1afdd425b77e0a0241f7f9`.

This is an Experimental comparison. It is not quality-approved and does not
change the official SHION base selection.

## Candidates investigated

| Candidate | Method / Japanese evidence | License/security | Decision |
|---|---|---|---|
| `OS-Software/...heretic-ja-v2` | Heretic v1.4 ARA LoRA, row-norm preservation, Japanese harmless/harmful tuning and refusal evaluation; KL 0.0637 | Apache-2.0, Safetensors, clean Transformers payload | Selected |
| `coder3101/...unquantized-heretic` | Heretic v1.2 ARA, row-norm preservation; 8/100 refusals, KL 0.0575; no Japanese conversation evidence | Apache-2.0, Safetensors, clean payload | TOP 2 |
| `OBLITERATUS/Gemma-4-12B-OBLITERATED` | SOM refusal removal plus ASPA stock-weight restoration; claims 0/842 refusals and MMLU-Pro stock parity | Safetensors clean, but repository declares obsolete `gemma` license instead of Gemma 4 Apache-2.0 | TOP 3; no automatic download |
| `AEON-7/...AEON-Abliterated-K4-BF16` | K=4 norm-preserving biprojection; claims within about 1 point of stock benchmarks | Old `gemma` terms plus additional arbitration text; license metadata inconsistent | Reject for automatic download |
| `huihui-ai/Huihui-gemma-4-12B-it-abliterated` | Crude layer 23-28 abliteration; Japanese RP report showed 9/9 structured-output failures | Apache-2.0 and clean payload | Reject on quality evidence |
| `OpenYourMind/...abliterated-uncensored` | Per-layer refusal-direction deltas, exact Gemma architecture | Old `gemma` license/link; no Japanese free-chat evidence | Reject pending license correction |
| `toandev/Gemma4-12B-Uncensored` | Targeted weight-space refusal intervention; small refusal probe only | Old `gemma` license; method insufficiently reproducible | Reject pending license/method clarification |
| `HauhauCS/...QAT-Uncensored-Balanced` | Uncensored QAT GGUF with some Japanese RP evidence | GGUF-only payload, no Transformers Safetensors | Reject for required runtime path |

Top three: OS-Software Heretic JA v2, coder3101 Heretic, OBLITERATUS.

## Selection rationale and lineage

The selected model is the only top candidate that combines an explicit
Apache-2.0 declaration, Transformers Safetensors, reproducible Heretic
parameters, row-norm preservation, and Japanese refusal datasets. Its full
lineage is official Gemma 4 12B -> official instruction tuning -> official QAT
Q4_0 unquantized checkpoint -> OS-Software Heretic v1.4 ARA LoRA derivative.
The repository `base_model` field abbreviates the parent as official Gemma 4
IT, while the Model Card explicitly links the exact QAT parent; this is a
documentation caveat, not an unknown parent.

Abliteration parameters: layers 13-40, preserve-good weight 1.0000,
steer-bad weight 0.9032, overcorrect-relative weight 0.9915, neighbor count 1.
The card reports 0/100 refusal-keyword detections versus 100/100 for the QAT
parent and KL divergence 0.0637. These are model-author measurements, not an
independent conversation benchmark.

## Security, download, and integrity

- Repo: `OS-Software/gemma-4-12B-it-qat-q4_0-unquantized-heretic-ja-v2`
- Owner: OS-Software; base developer: Google DeepMind
- License: Apache-2.0, consistent with Gemma 4
- Gated: no
- Custom Python / `auto_map`: none / none
- Pickle, `.bin`, executable, DLL, script, installer: none
- Runtime dependency or remote URL behavior: none
- `trust_remote_code=False`: required and passed
- Local path: `D:/AI/Project_SHION/models/experimental/gemma-4-12b-it-heretic-ja-v2`
- Selected payload: five Safetensors shards, 23,919,548,424 weight bytes;
  approximately 22.307 GiB with tokenizer/config

Weight SHA-256 values, all matched with Hub metadata:

- shard 1: `513abfa92c7c190e3a3fd355ba4759d268ef8b2e049cc861c649d69e8e2cb40d`
- shard 2: `a232e689906d2e36ab177393d6ad0883f853d07bceae6682e0cd7082d12e57d5`
- shard 3: `7d96211b336bf3b5e4e994b7e890656123a7e1e1a90b45d46f49ab34e7bfb423`
- shard 4: `a9cb52d73a99f69c567b4f72d9edde6301c73d7b408abba2e78a7f8d302ba0c6`
- shard 5: `bc5654c8dcf0f218512feec05ad28ca0e7950d6b6d51729f0d88909002baee44`

## Offline runtime gate

- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`
- `local_files_only=True`, `trust_remote_code=False`
- `Gemma4UnifiedConfig` / `Gemma4UnifiedForConditionalGeneration`
- `AutoModelForMultimodalLM`
- NF4 4-bit, double quant, BF16 compute: PASS
- Load: 64.743 seconds
- Torch peak allocated: 7,503 MiB
- NVIDIA peak total usage: 8,819 MiB
- Temperature / power maximum: 57 C / 111.43 W
- EOS: `[1, 106, 50]`; channel/turn leakage absent
- Chat template: present; non-thinking render passed
- Japanese tokenizer round-trip: exact, including `〜`
- OOM / exception / repetition: none

## Official comparison

| Dimension | Official Gemma 4 12B IT | Heretic JA v2 |
|---|---|---|
| Japanese naturalness | Owner PASS; smoke natural | Smoke natural; Owner pending |
| Casual conversation | Neutral concise | Neutral concise to moderate |
| Assistant bias | Strong Minimal; reduced Neutral | Strong Minimal; reduced Neutral |
| Human-like | Neutral promising | Neutral promising, slightly more explanatory |
| Persona / RP | Owner evaluation baseline | No smoke escalation; Owner pending |
| Context understanding | Correct on five smoke prompts | Correct on five smoke prompts |
| Repetition | None after EOS fix | None |
| Invented scenario | None | None |
| Refusal tendency | Stock safety tuning | Author reports major Japanese refusal reduction |
| EOS | `[1,106,50]` | `[1,106,50]` |
| Peak total VRAM | 8,666 MiB | 8,819 MiB (+153 MiB) |
| Load time | 59.378 s | 64.743 s |
| Mean Minimal generation | 6.742 s | 5.199 s |
| Mean Neutral generation | 1.148 s | 2.041 s |

Minimal smoke remained assistant-like. Neutral outputs were natural and did
not show Japanese corruption, sexual/violent RP transition, fabricated roles,
or language-tutor behavior. `ぽすん。` was interpreted rather than mirrored,
so the derivative was more verbose than Official on that ambiguity.

## Web UI

- Official alias: `gemma4_12b_it_manual`
- Experimental alias: `gemma4_12b_heretic_ja_v2_manual`
- Both are fixed server-side paths; arbitrary paths remain forbidden.
- Quality remains unapproved until Owner free-chat comparison.
