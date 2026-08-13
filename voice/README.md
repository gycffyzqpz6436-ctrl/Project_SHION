# Voice Prototype v0.1

This prototype keeps all executable environments, model weights, caches, temporary files, and generated audio below `SHION_DATA_ROOT` (default `D:\AI\Project_SHION`). Project_SHION contains only lightweight integration code, configuration, and documentation. It does not use or modify `training/.venv`.

## Fixed runtime

- Style-Bert-VITS2: 2.7.0, commit `d8148f3090ee5038ca7b4e4b327116c64467f952`, AGPL-3.0
- Python: 3.10
- PyTorch: 2.11.0+cu128
- torchaudio: 2.11.0+cu128
- Transformers: 4.48.3
- Accelerate: 1.2.1 (required by Transformers for the Japanese BERT `device_map="cuda"` load)
- CUDA wheel runtime: 12.8
- Device gate: NVIDIA RTX 5070, compute capability 12.0 (`sm_120`)

The runtime always sets Hugging Face and Transformers offline mode before synthesis. No CPU fallback is allowed by the prototype command.

## Commands

From the Project_SHION repository root:

```powershell
D:\AI\Project_SHION\runtime\voice-venv\py310-cu128\Scripts\python.exe voice\scripts\diagnose.py

D:\AI\Project_SHION\runtime\voice-venv\py310-cu128\Scripts\python.exe voice\scripts\synthesize.py `
  --text "……聞こえる？ お兄さん♪" `
  --output "D:\AI\Project_SHION\artifacts\voice\prototype-v0.1\line_01.wav"
```

Voice Tuning Console v0.2:

```powershell
D:\AI\Project_SHION\runtime\voice-venv\py310-cu128\Scripts\python.exe voice\server.py --port 8766
```

Open `http://127.0.0.1:8766`. The server always binds to `127.0.0.1`; there is no host or share option. Generated WAV files are written to `D:\AI\Project_SHION\artifacts\voice\voice-tuning`. Candidate and Owner-approved preset JSON files are deliberately separated under `voice/presets/`.

The same page includes Voice Model Manager. It discovers Style-Bert-VITS2 folders recursively below `D:\AI\Project_SHION\models\voice`, persists local registration state under `D:\AI\Project_SHION\data\voice`, and exposes only Ready models to the tuning dropdown. See `voice/docs/model_manager.md` before importing or reviewing a third-party model.

Generation controls are in `voice/config/prototype_v0_1.json`. Keep runtime/model/output paths under the configured external root.

## Boundaries

- No Gemma integration is implemented in v0.1.
- Do not place models, WAV files, caches, virtual environments, or training material in this repository.
- Do not treat JVNV F1/F2 as a custom SHION voice. They are comparison/prototype voices only.
