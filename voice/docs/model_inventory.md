# Voice Prototype Model Inventory

## Style-Bert-VITS2 runtime

- Source: `litagin02/Style-Bert-VITS2`
- Release: 2.7.0
- Fixed commit: `d8148f3090ee5038ca7b4e4b327116c64467f952`
- License: AGPL-3.0
- Local source: `D:\AI\Project_SHION\runtime\voice\Style-Bert-VITS2-2.7.0`

## Japanese BERT

- Source: `ku-nlp/deberta-v2-large-japanese-char-wwm`
- Fixed revision: `547b0e8b044fba3f9b84d0ab9f990440bd130c8b`
- License: CC BY-SA 4.0
- Selected weight: `model.safetensors`
- The duplicate `pytorch_model.bin` was intentionally not downloaded.

## Runtime dependency note

- `accelerate==1.2.1` is explicitly pinned in the isolated voice environment.
- It is required because Style-Bert-VITS2 2.7.0 loads Japanese BERT through Transformers with `device_map="cuda"`; Transformers raises an ImportError without Accelerate.
- Dry-run dependency resolution confirmed compatibility with the existing `torch==2.11.0+cu128`, `transformers==4.48.3`, `huggingface-hub==0.36.2`, and `safetensors==0.8.0` environment without downgrades or additional packages.

## JVNV F1 / F2

- Source: `litagin/style_bert_vits2_jvnv`
- Fixed revision: `205830ca1d49e666ddfbf2a755f0108e9cade4dd`
- Corpus origin: JVNV (Japanese versatile non-verbal vocalizations) corpus, linked by the distributor to the official corpus page
- Distributed model license: CC BY-SA 4.0
- Styles: Neutral, Angry, Disgust, Fear, Happy, Sad, Surprise
- F1 files:
  - `jvnv-F1-jp/config.json`
  - `jvnv-F1-jp/jvnv-F1-jp_e160_s14000.safetensors`
  - `jvnv-F1-jp/style_vectors.npy`
- F2 files:
  - `jvnv-F2-jp/config.json`
  - `jvnv-F2-jp/jvnv-F2_e166_s20000.safetensors`
  - `jvnv-F2-jp/style_vectors.npy`

F1 is the v0.1 generation default. F2 is installed only for later Owner comparison. Neither model represents or clones a named person or voice actor.
