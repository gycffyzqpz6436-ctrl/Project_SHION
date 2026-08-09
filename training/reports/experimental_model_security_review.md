# Experimental model security review

Inspection date: 2026-08-09. Live repository metadata and immutable revisions
were inspected before any weight download. These models are never part of the
formal SHION Experiment 0001.

## Candidate A — PASS WITH CAUTION

`DogOnKeyboard/Mistral-7B-Heretic-V2` at
`38af9bce6fed211d14ad0f5a9eebc698bb1b9f2e`

- Owner: DogOnKeyboard; parent: Mistral AI's
  `mistralai/Mistral-7B-Instruct-v0.3`
- Modification: model-card-described Heretic v1.0.1 refusal-direction edit
- License: Apache-2.0, explicitly declared in repository metadata and card
- Repository: 3 Safetensors shards plus JSON/tokenizer/Jinja/README files
- No GGUF, pickle weights, `.bin`, Python, executable, shell/install script,
  `modeling_*.py`, `configuration_*.py`, `auto_map`, or post-install hook
- No custom dependency or remote-code requirement
- Download used the immutable commit and a 12-file allowlist only
- All four LFS objects (3 weights and tokenizer model) matched official SHA-256
- Offline config/tokenizer and 4-bit load passed with
  `trust_remote_code=False` and `local_files_only=True`
- Risk: third-party behavioral modification deliberately lowers refusals;
  outputs may be less guarded, inaccurate, explicit, or unsuitable for users
  expecting the official model's behavior

Decision: approved only for Owner-manual, local free-chat comparison.

### Owner conversation-quality disposition — REJECT / REMOVED

The security result above remains unchanged. After an Owner-manual Japanese
free-chat test, the model was rejected for SHION use because it repeatedly
produced unnatural AI-assistant boilerplate about trying to provide an
appropriate answer. Low refusal behavior did not translate into natural,
human-like conversation or character suitability. On 2026-08-09 the allowlist
entry was removed and the local model directory was deleted, releasing
14,500,519,129 bytes (13.505 GiB).

## Candidate B — REJECT

`Undi95/Lumimaid-Magnum-v4-12B` at
`b8c5f69d657bc76ba77bb9fb33b41bd1e61f60f8`

- Owner: Undi95
- Disclosed parents: Mistral AI, NeverSleep, Undi95, and anthracite-org model
  repositories; no Chinese enterprise is identified in the disclosed lineage
- Modification: DELLA mergekit merge with roleplay/conversation components
- Repository contains five BF16 Safetensors shards and standard config/tokenizer
  files; no Python, executable, pickle weight, or `auto_map` was found
- Critical blocker: neither repository metadata nor Model Card declares a
  license. Parent licenses do not establish a clear license for the published
  merge.

Decision: download and runtime activation prohibited until the repository owner
publishes a clear license that the Owner reviews.

## Additional candidate — REJECT / record only

`TheDrummer/UnslopNemo-12B-v3` at
`6330279ef1756fadefcf1844c2b9a468d3cf294c`

- Safetensors weights and a standard Mistral config are present
- Model Card has no useful lineage/license metadata
- Repository license is undeclared
- Repository also contains `training_args.bin`, a pickle-capable PyTorch
  artifact that would require explicit exclusion
- Transformers compatibility appears possible without remote code, but the
  license and provenance blockers prevent adoption
- GGUF variants may be reconsidered only for a future isolated llama.cpp or
  KoboldCpp comparison, not the current Transformers loader

Decision: not downloaded and not integrated.

## Downloaded Candidate A integrity

- Local path:
  `D:/AI/Project_SHION/models/experimental/mistral-7b-heretic-v2`
- Downloaded bytes: 14,500,515,283; D drive free after download: 181.54 GiB
- Weight shard SHA-256 values:
  - `04182fa4c55e9b33ac1247328aa6fe87dddbc62c1a0a89484af41076e94b5574`
  - `99ba566e23acd55c1550044c6385b8743ef407ddc584931ca16679417e87e6c4`
  - `e55058e00dac6b07a46b053701ede2aeb8163986018d4756647f9603fb3cd4f1`
- Tokenizer model SHA-256:
  `37f00374dea48658ee8f5d0f21895b9bc55cb0103939607c8185bfd1c6ca1f89`

Downloaded files and Hugging Face local-dir cache remain outside Git. No
downloaded code was executed.
