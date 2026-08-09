# Experimental Japanese Base Research — 2026-08-09

## Decision

The first download candidate is the official `google/gemma-4-12b-it`, pinned
to `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`. It is a comparison candidate,
not an approved SHION base. The previous Heretic, Impish, Shisa, Qwen ERP, and
Qwen JP Uncensored quality rejections remain in force.

## Gemma 4 license finding

Google's Gemma Terms page explicitly routes Gemma 4 to a separate license.
That Gemma 4 license is Apache License 2.0 as of 2026-04-01. Accordingly,
private local use, fine-tuning, LoRA creation, commercial use, merged models,
and redistribution are permitted. Redistribution must include Apache-2.0,
mark modified files, preserve applicable notices/attribution, and carry any
upstream NOTICE. Trademark rights are not granted. Generated outputs are not
restricted by an additional Gemma-specific output clause.

Older Gemma Terms and their prohibited-use policy must not be incorrectly
applied to Gemma 4. Conversely, a derivative repository tagged `gemma` instead
of `apache-2.0` is metadata-inconsistent with the new upstream license and was
not selected without clarification, even though its upstream rights are now
more permissive.

Primary sources:

- https://ai.google.dev/gemma/terms
- https://ai.google.dev/gemma/apache_2
- https://huggingface.co/google/gemma-4-12b-it

## Candidate comparison (12 candidates)

Ratings combine model cards, lineage/security evidence, published Japanese
tests, and prior local Owner results. `Unknown` means no defensible Japanese
free-chat evidence, not poor benchmark performance.

| Candidate | Origin / lineage | License | Japanese grammar / natural / casual / emotional / RP / character / slang / human-like | Low refusal | Assistant bias | Security decision |
|---|---|---|---|---|---|---|
| `google/gemma-4-12b-it` | Google US; Gemma 4 base -> official IT | Apache-2.0 | Strong / Strong / Moderate / Strong / Strong / Strong / Moderate / Strong | Moderate | Moderate | PASS |
| `google/gemma-4-12b` | Google US; official base | Apache-2.0 | Strong / Unknown / Weak / Unknown / Weak / Weak / Unknown / Unknown | Unknown | Low, but no chat tuning | PASS; not chat-ready |
| `Qwen/Qwen3.5-9B` | Qwen/Alibaba China; official base -> unified IT | Apache-2.0 | Strong / Strong / Strong / Strong / Strong / Strong / Strong / Strong | Moderate | Moderate | PASS; origin recorded |
| `tokyotech-llm/Llama-3.1-Swallow-8B-Instruct-v0.3` | Tokyo Tech/LLM-jp; Llama 3.1 plus Japanese continual pretraining/SFT | Llama 3.1 plus dataset-derived Gemma terms | Strong / Moderate / Moderate / Moderate / Moderate / Moderate / Moderate / Moderate | Weak | Strong | PASS WITH CAUTION |
| `elyza/Llama-3-ELYZA-JP-8B` | ELYZA Japan; Llama 3 8B Instruct plus Japanese pretraining/SFT | Llama 3 Community | Strong / Moderate / Moderate / Moderate / Moderate / Moderate / Moderate / Moderate | Weak | Strong | PASS WITH CAUTION |
| `OBLITERATUS/Gemma-4-12B-OBLITERATED` | Gemma 4 IT; two-pass refusal-vector surgery | Repository says `gemma`, upstream is Apache-2.0 | Strong / Moderate / Unknown / Unknown / Moderate / Moderate / Unknown / Unknown | Strong | Unknown | PASS WITH CAUTION; metadata mismatch |
| `AEON-7/Gemma-4-12B-it-AEON-Abliterated-K4-BF16` | Gemma 4 IT; K4 abliteration | Repository says `gemma`, upstream is Apache-2.0 | Strong / Unknown / Unknown / Unknown / Unknown / Unknown / Unknown / Unknown | Strong | Unknown | PASS WITH CAUTION; little quality evidence |
| `OpenYourMind/gemma-4-12B-it-abliterated-uncensored` | Gemma 4 IT; abliterated derivative | Repository says `gemma`, upstream is Apache-2.0 | Strong / Unknown / Unknown / Unknown / Moderate / Unknown / Unknown / Unknown | Strong | Unknown | PASS WITH CAUTION; method evidence limited |
| `toandev/Gemma4-12B-Uncensored` | Gemma 4 IT; refusal-research derivative | Repository says `gemma`, upstream is Apache-2.0 | Strong / Unknown / Unknown / Unknown / Unknown / Unknown / Unknown / Unknown | Strong | Unknown | PASS WITH CAUTION; no Japanese free-chat evidence |
| `ValiantLabs/gemma-4-12B-it-Esper4` | Gemma 4 IT; creative fine-tune | Apache-2.0 | Strong / Moderate / Unknown / Strong / Strong / Strong / Unknown / Moderate | Unknown | Unknown | PASS WITH CAUTION; low adoption/evidence |
| `HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced` | Gemma 4 IT QAT derivative | Repository says `gemma`; GGUF only | Strong / Moderate / Unknown / Unknown / Strong / Unknown / Unknown / Unknown | Strong | Unknown | REJECT for Transformers/PEFT path (GGUF only) |
| `SicariusSicariiStuff/Impish_Nemo_12B` | Mistral Nemo IT; multi-stage RP SFT | Apache-2.0 | Weak / Weak / Weak / Weak / Moderate / Weak / Weak / Weak | Strong | Moderate | REJECTED by Owner; historical only |

## Top five and top three

Top five, in order:

1. `google/gemma-4-12b-it` — best balance of Japanese reputation, coherent
   official chat tuning, clean lineage/security, and future QLoRA suitability.
2. `Qwen/Qwen3.5-9B` — strongest published Japanese RP result among compared
   stock checkpoints and excellent 12GB fit, but Chinese base origin and prior
   Qwen-family assistant/behavior failures require a fresh Owner gate.
3. `tokyotech-llm/Llama-3.1-Swallow-8B-Instruct-v0.3` — strongest explicit
   Japanese training provenance; likely more assistant/instruction biased.
4. `OBLITERATUS/Gemma-4-12B-OBLITERATED` — low refusal with claimed stock
   benchmark parity, but Japanese natural-chat evidence and license metadata
   correction are missing.
5. `ValiantLabs/gemma-4-12B-it-Esper4` — creative/character intent and correct
   license, but very limited adoption and independent Japanese evidence.

Top three are official Gemma 4 12B IT, official Qwen3.5 9B, and Swallow 8B.
Official Gemma is selected first because the present goal is conversational
substrate quality rather than uncensoring strength.

## Japanese evidence and limits

A Japanese RP comparison published 2026-06-19 found official Qwen3.5-9B Q8
highest on its constrained nine-case test; official Gemma 4 Q4/Q8 remained
stable and roughly matched a strong Gemma heretic variant, while several
abliterated Gemma derivatives failed structure or content. This is useful
quality evidence but not a natural free-chat benchmark, so Owner testing in
Minimal and Neutral modes remains decisive.

Source: https://zenn.dev/kanaianzen/articles/e87625abac4547

## Download and integrity

- Local path: `D:/AI/Project_SHION/models/experimental/gemma-4-12b-it`
- Weight: `model.safetensors`, 23,919,549,408 bytes
- Total selected runtime payload: approximately 22.31 GiB plus 32 MiB tokenizer
- Hub revision metadata: `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`
- Weight SHA-256: `5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d`
- Local SHA-256 matches the Hugging Face download/Xet metadata
- No `.py`, `.bin`, pickle, GGUF, DLL, EXE, BAT, PS1, shell/install script,
  custom dependency, `auto_map`, or external runtime behavior is present

## Offline validation

- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`
- `local_files_only=True`, `trust_remote_code=False`
- Config: `Gemma4UnifiedConfig`, `gemma4_unified`, 262,144 positions
- Architecture: `Gemma4UnifiedForConditionalGeneration`
- Tokenizer: `GemmaTokenizer`; Japanese encode/decode passed (wave dash is
  Unicode-normalized from `〜` to `～`)
- Chat template: present; `enable_thinking=False` supported and required
- Custom code / `auto_map`: absent
- 4-bit NF4 double quant / BF16 load, VRAM, release, and five-prompt smoke:
  pending because an Owner-started `app/server.py` held about 7.7 GiB VRAM.
  That process was deliberately not terminated.

## Web UI and protected artifacts

The server-side alias is `gemma4_12b_it_manual`, currently disabled until the
NF4 GPU gate passes. It uses the fixed path and
revision, `AutoModelForMultimodalLM`, offline/local-only loading,
`trust_remote_code=False`, NF4 double quant with BF16 compute, and non-thinking
generation. Minimal and Neutral modes are available; Canonical is unchanged.
This registration is Experimental / Owner Manual Test and is not a quality
approval.

The two rejected Qwen models are retained for comparison. No model directory
was deleted. Golden, Database, Canonical Documentation, Experiment 0001,
Baseline, Evaluation, checkpoints, adapters, and Official Mistral models were
not modified.

## Remaining gate

Stop the existing Owner Web UI with Ctrl+C, then ask Codex to resume the short
NF4 load/smoke gate. After that gate passes, Codex will enable the alias and the
exact Owner command will be:

```powershell
cd C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
training\.venv\Scripts\python.exe app\server.py --model gemma4_12b_it_manual
```
