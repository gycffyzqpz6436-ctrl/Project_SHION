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

