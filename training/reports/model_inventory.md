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

## Experimental model — free-chat comparison only

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
- Intended use: FREE CHAT COMPARISON ONLY; excluded from
  `shion_sft_exp_0001`, Golden, Baseline, Evaluation, and training

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
