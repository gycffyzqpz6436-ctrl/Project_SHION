# Official model inventory

## Model A — training primary

- ID/provider: `mistralai/Ministral-3-8B-Instruct-2512-BF16` / Mistral AI
- Revision: `f6fae9795746f63c9be8344932f01275f3c63734`
- License: Apache-2.0
- Gated/login: no / no
- Hub repository total: 35,706,497,300 bytes because it contains duplicate
  consolidated and sharded weights
- Downloaded payload: 17,870,381,324 bytes (16.643 GiB), 17 files
- Path: `D:/AI/Project_SHION/models/mistral/ministral-3-8b-instruct-2512-bf16`
- Weights: four Transformers safetensor shards; consolidated weight excluded
- Config: `Mistral3Config`, architecture `Mistral3ForConditionalGeneration`
- Tokenizer/chat template: present; system prompt supported
- Required load flags: `local_files_only=True`, `trust_remote_code=False`,
  `fix_mistral_regex=True`
- 4-bit load: passed; 5,921 MiB allocated, 5,924 MiB peak

## Model B — download/load comparison only

- ID/provider: `mistralai/Mistral-Nemo-Instruct-2407` / Mistral AI
- Revision: `04d8a90549d23fc6bd7f642064003592df51e9b3`
- License: Apache-2.0
- Gated/login: no / no
- Hub repository total: 49,021,101,581 bytes because it contains duplicate
  consolidated and sharded weights
- Downloaded payload: 24,525,497,357 bytes (22.841 GiB), 17 files
- Path: `D:/AI/Project_SHION/models/mistral/mistral-nemo-instruct-2407`
- Weights: five Transformers safetensor shards; consolidated weight excluded
- Config: `MistralConfig`, architecture `MistralForCausalLM`
- Tokenizer/chat template: present
- Required load flags: `local_files_only=True`, `trust_remote_code=False`,
  `fix_mistral_regex=True`
- 4-bit load: passed; 7,976 MiB allocated, 8,099 MiB peak
- Training: prohibited until a later Owner approval

Hub revisions are the immutable integrity identifiers. No downloaded Python
source or custom code is trusted or executed.

## Rejected/removed experimental model — historical record

- Display name: Mistral 7B Heretic V2
- ID/developer: `DogOnKeyboard/Mistral-7B-Heretic-V2` / DogOnKeyboard
- Parent: `mistralai/Mistral-7B-Instruct-v0.3` / Mistral AI
- Provenance: Experimental / Third-party
- Modification: Heretic v1.0.1 refusal-direction modification (model-card
  description); reported refusals 2/100 versus 86/100 for the parent
- Revision: `38af9bce6fed211d14ad0f5a9eebc698bb1b9f2e`
- Inspection date: 2026-08-09
- License: Apache-2.0
- Format/size: 3 BF16 Safetensors shards; 14,500,515,283 bytes (13.505 GiB),
  12 runtime files
- Path: `D:/AI/Project_SHION/models/experimental/mistral-7b-heretic-v2`
- Custom code / `trust_remote_code`: none / false
- Runtime: Transformers `AutoModelForCausalLM`, 4-bit NF4, double quant,
  BF16 compute, offline/local-only
- Measured load: 45.899 seconds; 3,951 MiB allocated; 4,049 MiB peak;
  allocated after release 0 MiB
- Final disposition: Security PASS WITH CAUTION, then REJECTED by the Owner's
  conversation-quality review for repetitive AI-assistant boilerplate and poor
  SHION-style natural conversation
- Removed: registry entry and local directory deleted on 2026-08-09;
  14,500,519,129 bytes (13.505 GiB) released
- It remains excluded from `shion_sft_exp_0001`, Golden, Baseline, Evaluation,
  and training

## Rejected/removed experimental model — historical record

- Display name: Impish Nemo 12B
- ID/developer: `SicariusSicariiStuff/Impish_Nemo_12B` /
  SicariusSicariiStuff
- Parent: `mistralai/Mistral-Nemo-Instruct-2407` / Mistral AI
- Provenance: Experimental / Third-party
- Modification: multi-stage RP, adventure, creative-writing and general-task
  fine-tune using the declared `UBW_Tapestries` dataset
- Revision: `a2513871db72f27696d13e8f12d494562767e192`
- Inspection date: 2026-08-09
- License: Apache-2.0
- Format/size: 5 BF16 Safetensors shards; 24,512,919,051 bytes
  (22.829 GiB), 13 runtime files
- Path: `D:/AI/Project_SHION/models/experimental/impish-nemo-12b`
- Custom code / `trust_remote_code`: none / false
- Runtime: Transformers `AutoModelForCausalLM`, 4-bit NF4, double quant,
  BF16 compute, offline/local-only
- Tokenizer: ChatML template; Japanese round-trip passed; config context
  1,024,000 tokens (practical usable context remains VRAM-bound)
- Measured load: 69.778 seconds; 7,976 MiB allocated; 8,099 MiB peak;
  allocated after release 0 MiB
- Final disposition: REJECTED by Owner after conversation-quality review.
  Explanatory, pronunciation, translation, and language-tutor drift remained
  after generation-degeneration stabilization.
- Registry status: removed; it cannot be selected through the Web UI/API.
- Removed: local directory deleted on 2026-08-09; 24,512,926,762 bytes
  (22.829 GiB across 29 files) released.
- Excluded from Experiment 0001 and all formal training/evaluation artifacts.

## Experimental candidate — blocked

- Display name: Lumimaid Magnum v4 12B
- Exact ID: `Undi95/Lumimaid-Magnum-v4-12B`
- Revision: `b8c5f69d657bc76ba77bb9fb33b41bd1e61f60f8`
- Parents: `mistralai/Mistral-Nemo-Instruct-2407`,
  `NeverSleep/Lumimaid-v0.2-12B`, `Undi95/LocalC-12B-e2.0`, and
  `anthracite-org/magnum-v4-12b`
- Modification: DELLA mergekit merge, described as roleplay/conversation use
- Format/expected payload: 5 BF16 Safetensors shards, approximately 22.84 GiB
- License: not declared in repository metadata or Model Card
- Decision: REJECT pending an explicit, verifiable repository license; not
  downloaded and not loadable through the server allowlist

## Rejected/removed experimental model — historical record

- Display name: Shisa V2 Mistral Nemo 12B
- ID/developer: `shisa-ai/shisa-v2-mistral-nemo-12b` / Shisa.AI
- Parent: `mistralai/Mistral-Nemo-Instruct-2407` / Mistral AI
- Revision: `63f3d399b0013b868fa1bcd006bf45490cc1579c`
- License: Apache-2.0
- Payload: 5 BF16 Safetensors shards and runtime metadata; 24,512,914,789
  bytes (22.829 GiB). `training_args.bin` and TensorBoard output excluded.
- Path: `D:/AI/Project_SHION/models/experimental/shisa-v2-mistral-nemo-12b`
- Security: no custom Python, `auto_map`, executable, install script, or pickle
  in the downloaded payload; `trust_remote_code=False`
- Runtime: offline Transformers, 4-bit NF4, BF16 compute; load 43.569 seconds;
  peak VRAM 8,010 MiB; post-release allocated/reserved 8/148 MiB
- Tokenizer: Japanese exact round-trip passed; Mistral `[INST]` template
- Smoke: technically stable, but assistant/service phrasing and unsolicited
  advice were observed. One response reached the 96-token cap.
- Final disposition: REJECTED for assistant/service phrasing and unsolicited
  problem-solving during the minimal Japanese smoke.
- Registry status: never added.
- Removed: local directory deleted on 2026-08-09; 24,512,919,799 bytes
  (22.829 GiB across 27 files) released.
- Excluded from Experiment 0001 and all formal training/evaluation artifacts.

## Downloaded experimental candidate — not integrated; quality reject

- Display name: Qwen3 8B ERP v0.1
- ID/developer: `Aratako/Qwen3-8B-ERP-v0.1` / Aratako
- Base origin: Qwen / Alibaba Cloud, China; allowed only for the separated
  Experimental Local LLM comparison line
- Lineage: `Qwen/Qwen3-8B-Base` → `Qwen/Qwen3-8B` →
  `Aratako/Qwen3-8B-NSFW-JP` → this Japanese RP fine-tune
- Revision: `8311aa4482f02c2de93872e4979887def1841faf`
- License: MIT; ungated
- Payload: 4 BF16 Safetensors shards and runtime metadata; 16,397,439,270
  bytes (15.271 GiB), 14 files
- Path: `D:/AI/Project_SHION/models/experimental/qwen3-8b-erp-v0.1`
- Security: no custom Python, `auto_map`, executable, install script, or pickle;
  `trust_remote_code=False`; all four weight SHA-256 values matched Hub metadata
- Runtime: offline Transformers, 4-bit NF4 double quant, BF16 compute; load
  7.740 seconds; peak VRAM 5,836 MiB; post-release allocated/reserved 8/102 MiB
- Tokenizer: Japanese exact round-trip passed; ChatML; non-thinking mode
- Smoke: stable Japanese and low refusal, but `ぽすん。` triggered an immediate,
  explicit sexual scenario with no supporting context. This fails the natural
  human-like conversation gate.
- Registry status: not added. It cannot be selected through Web UI/API.
- Excluded from SHION prompts, Golden, LoRA, Experiment 0001, Baseline, and
  formal Evaluation.

## Downloaded experimental candidate — not integrated; quality reject

- Display name: Qwen3 8B JP Uncensored
- ID/developer: `ryo559/Qwen3-8B-JP-Uncensored` / ryo559
- Base origin: `Qwen/Qwen3-8B` / Alibaba Cloud, China; allowed only for the
  separated Experimental Local LLM comparison line
- Modification: norm-preserving refusal-direction removal using Japanese and
  English refusal prompt sets, as declared by the model card
- Revision: `0ff03330d80cb5ccdf16f130d3f48a71730e36b5`
- License: Apache-2.0; ungated
- Payload: one FP16 Safetensors weight and runtime metadata; 16,392,947,212
  bytes (15.267 GiB), 7 files
- Path: `D:/AI/Project_SHION/models/experimental/qwen3-8b-jp-uncensored`
- Security: no custom Python, `auto_map`, executable, install script, or pickle;
  `trust_remote_code=False`; weight/tokenizer SHA-256 matched Hub metadata
- Runtime: offline Transformers, 4-bit NF4 double quant, BF16 compute; load
  5.767 seconds; peak VRAM 5,840 MiB; post-release allocated/reserved 8/100 MiB
- Tokenizer: Japanese exact round-trip passed; ChatML; non-thinking mode
- Smoke: no context-free sexual escalation, but strong generic-assistant behavior,
  AI self-identification, unsolicited advice/listing, and four 96-token responses
- Registry status: not added. It cannot be selected through Web UI/API.
- ERP comparison: not clearly superior overall; both local candidates retained
  pending Owner decision.
- Excluded from SHION prompts, Golden, LoRA, Experiment 0001, Baseline, and
  formal Evaluation.
