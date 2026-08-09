# Experimental model candidate review — 2026-08-09

The selection separated low-refusal behavior from natural conversation and RP
quality. All candidates are Mistral NeMo derivatives rather than Chinese-origin
base models. Repository metadata, immutable commits, lineage, licenses, and
complete file manifests were inspected before download.

## GreenerPastures/Golden-Curry-12B — PASS, not selected

- Revision: `7e4e571445465e26c8379bdc85499caffb0a05a0`
- License: Apache-2.0; ungated; parent:
  `IntervitensInc/Mistral-Nemo-Base-2407-chatml`
- Five BF16 Safetensors shards; no Python, pickle, executable, `auto_map`, or
  remote-code requirement
- Strong fit evidence: narrative-fiction continued training followed by
  instruct, RP, and preference-alignment stages; card targets persona
  persistence, dynamic storytelling, emotional dialogue, interactive fiction,
  and character simulation
- Not selected: complex 18-dataset mixture makes behavior attribution harder,
  and the card declares English rather than multilingual training

## SicariusSicariiStuff/Impish_Nemo_12B — PASS, selected

- Revision: `a2513871db72f27696d13e8f12d494562767e192`
- License: Apache-2.0; ungated; parent:
  `mistralai/Mistral-Nemo-Instruct-2407`
- Five BF16 Safetensors shards; no Python, pickle, executable, `auto_map`, or
  remote-code requirement
- Strong fit evidence: intended for RP, adventure, creative writing and general
  tasks; the card describes strong character agency, reduced positivity bias,
  dynamic response length, and deliberate preservation of general capability
- Caveat: RP and naturalness claims are publisher claims; Japanese quality and
  assistant-boilerplate frequency require Owner-manual tests

## nbeerbower/Vitus-mistral-nemo-12B — PASS, not selected

- Revision: `8f6f73d236815f8b5c6d9afdf039a06400d93b20`
- License: Apache-2.0; ungated; parent:
  `nbeerbower/Schreiber-mistral-nemo-12B`
- Five BF16 Safetensors shards; no Python, pickle, executable, `auto_map`, or
  remote-code requirement
- Fit evidence: human-writing DPO is relevant to avoiding generic machine prose
- Not selected: RP, character persistence and low-refusal goals are less
  directly documented than for the selected model

## DarwinAnim8or/TinyRP-12B — PASS security, REJECT suitability

- Revision: `ac1ff82cb3dc817916372e7f7b18260e6ae78c70`
- License: Apache-2.0; ungated; parent: `nvidia/Mistral-NeMo-12B-Base`
- Five F16 Safetensors shards; no Python, pickle, executable, `auto_map`, or
  remote-code requirement
- RP focus is strong, but the card explicitly says it cannot act as a true
  assistant or agent and has only one RP mode
- Rejected because SHION also requires basic technical and general-dialogue
  competence

## Selected-model integrity and runtime

- Downloaded only 13 allowlisted runtime files; images, presets, GGUF, and
  unrelated artifacts were excluded
- Download size: 24,512,919,051 bytes (22.829 GiB)
- All five weight shard hashes and the tokenizer hash matched Hub LFS metadata
- Offline config/tokenizer load and Japanese encode/decode passed
- Chat template: ChatML; EOS `<|im_end|>` ID 2; PAD `<pad>` ID 10
- Offline 4-bit NF4/BF16 load passed: 7,976 MiB allocated, 8,099 MiB peak,
  69.778 seconds; allocated after release 0 MiB
- No generation, training, Baseline, or formal Evaluation was performed
