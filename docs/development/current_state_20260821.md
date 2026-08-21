# Project SHION Current State Audit — 2026-08-21

Status: formal repository and working tree audited

## Repository authority

- Formal repository: `gycffyzqpz6436-ctrl/Project_SHION`
- Local formal checkout: `C:/Users/PC/Documents/ChatGPT/Project_SHION/official-main`
- Branch: `main`
- Audited HEAD / `origin/main`: `06d08f8eccd318e1defb0aab88708fc47140f38a`
- Ahead / behind at audit: `0 / 0`

The parent `Project_SHION` directory is not the formal checkout. Repository
commands and documentation changes must run inside `official-main`.

At audit time the formal checkout also contained uncommitted Local STT/Desktop
Companion work. Those files are Owner work in progress, are not part of the
audited formal HEAD, and were deliberately not modified or staged by this state
review.

## Implemented at formal HEAD

- local SHION Web Chat and allowlisted offline model runtime;
- `ShionRuntime`, orchestrator, session/state, model loader and tool boundaries;
- persistent SQLite conversations, response versions and self-correction;
- reviewed local long-term Memory controls with automatic promotion disabled;
- Voice service integration, persistent voice registry/artifacts, and
  Owner-approved Nene V3 / Bright default;
- official static 2D character assets and Character renderer boundary;
- Desktop Companion first executable slice;
- Tailscale-aware access support under a separate network policy;
- dataset candidate/review/approval tooling and fixed training/evaluation assets.

Image generation, Vision, crawler ingestion, Live2D, and general external
knowledge integration are not active SHION capabilities. The disabled tool
registry entries are extension points, not evidence of implementation.

## Conversation model decision

Base-model exploration is closed. Official Gemma 4 12B IT at revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` is the Experiment 0002 training
foundation. Gemma 4 12B Heretic JA v2 remains an Experimental Owner-manual
low-refusal comparison only. Mistral/Nemo/Qwen and other results remain historical
records; they are not active base-selection work.

The repository preserves rejected/removed inventories and reports for Heretic V2,
Impish Nemo, Shisa V2 Mistral Nemo, Qwen ERP, Qwen JP Uncensored, and related
candidates. Security/runtime findings remain separate from Owner quality results.

## Dataset and Experiment 0001

- Formal Golden: 200 Owner-approved records, `shion_000101`–`shion_000300`.
- Golden source files: batches 0003 and 0004.
- Database: `dataset/database/shion_database.jsonl`, 438 lineage records at audit.
- Derived Experiment 0001 training data: 200 records.
- Golden, Database, and Canonical Documentation were not modified by this audit.

Experiment 0001 (Ministral 3 8B) completed its bounded Smoke only: four records,
two steps, loss 3.449609 to 3.384998, peak VRAM 11,791 MiB, max 54 C and
194.31 W, mean step 3.763 seconds, adapter save/reload PASS. No Full Training is
recorded. The repository defines a 36-prompt A/B Baseline plan, but contains no
evidence that the 72-response manual Baseline was completed; status is therefore
UNVERIFIED rather than inferred.

## Experiment 0002

Experiment 0002 is preparation/design only. The pinned model and tokenizer pass
offline static loading and all 200 records receive non-empty assistant-only masks.
Gemma-tokenized length is 46–290, so max length 1024 preserves all records.
RTX 5070 12 GB QLoRA feasibility remains a blocking Runtime Gate because the 8B
Experiment 0001 Smoke nearly exhausted the same GPU. See the dedicated
[preparation report](../../training/reports/shion_sft_exp_0002_gemma4_preparation.md).

## Image decision and integration roadmap

Animagine XL 4.0 Opt remains Security/Runtime PASS, Owner Visual Quality REJECT,
and not adopted. Runtime success is not model suitability. The next image task is
an audit of the Owner PC's existing Stable Diffusion environment, not a new model
search or installation. The audit must inventory runtime/frontend, Python,
PyTorch/CUDA, API/port, model/checkpoint/VAE/LoRA/ControlNet/IP-Adapter, output and
storage paths, licenses, and stability before a `StableDiffusionAdapter` design.

Future image output belongs in the same typed conversation timeline. Edits must
reference an existing image artifact and become structured intent (img2img,
inpaint, pose, expression, clothes, or background) rather than silently replacing
history.

## Development order

1. Experiment 0002 Gemma-specific static module/config validation.
2. Owner-approved bounded longest-record and two-step QLoRA Smoke.
3. Baseline/evaluation artifact review and Full Training preflight; Full Training
   remains a separate Owner-manual command and approval.
4. Stable Diffusion environment audit and isolated adapter architecture.
5. Conversation timeline image parts, explicit exports, and dataset-candidate
   export through Owner review only.
6. Continue reviewed Memory/knowledge separation and add crawler provenance only
   behind an independent service gate.
7. Vision input, then presentation/Live2D and mobile-client refinements through
   independent privacy, security and lifecycle gates.

## Protection boundary

This audit does not authorize or perform Full Training, Baseline, long GPU work,
model download, model-weight edits, Golden/Database/Canonical edits, Stable
Diffusion changes, network exposure changes, Tailscale changes, or use of private
conversation content as training data. Generated outputs, checkpoints, adapters,
models, caches, secrets, conversations, and private artifacts remain outside Git.
