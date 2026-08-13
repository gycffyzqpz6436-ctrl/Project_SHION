# Voice Model Manager

Voice Model Manager scans `%SHION_DATA_ROOT%\models\voice` recursively. No Python or JSON edit is needed when a new Style-Bert-VITS2 model is placed under that root.

## Required model structure

One folder must contain exactly one supported weight (`.safetensors`, `.pth`, or `.pt`), `config.json`, and `style_vectors.npy`. Styles and speaker names are read from `config.json`. Missing files are shown as **Incomplete**; malformed config or ambiguous multiple weights are **Invalid**.

Safetensors is preferred. The Manager recognizes legacy Style-Bert-VITS2 weight suffixes for compatibility, but it never executes downloaded code.

## Local folder

1. Place the model below `%SHION_DATA_ROOT%\models\voice` without overwriting an existing folder.
2. Open **Add Local Model** and enter/select that folder.
3. Select **Validate & Register**, review the discovered speaker/styles/files and license status.
4. Select **I reviewed the model license** only after checking the source terms.
5. Run **Test Voice**. A successful CUDA synthesis marks the model tested. It becomes **Ready** only when structure, license review, test, and enabled state all pass.

## Hugging Face

1. Enter an exact `owner/repository` and optional revision.
2. **Scan / Preview** resolves a fixed commit, displays repository license, candidate folders, file list, and size. Preview does not download weights.
3. Review the license and choose one detected candidate.
4. **Download selected candidate** requires explicit confirmation. It downloads only the selected folder into `%SHION_DATA_ROOT%\temp\voice`, then atomically moves the completed folder under `%SHION_DATA_ROOT%\models\voice\huggingface`.
5. Hugging Face cache is fixed to `%SHION_DATA_ROOT%\cache\huggingface\hub`. Existing fixed-revision destinations are reused.

Changing the Repo ID clears the previous repository's saved revision and candidates. Download revalidates that the exact 40-character Preview SHA still exists in the selected repository. If it no longer exists, the UI displays **Saved revision is no longer available.** and offers **Refresh repository revision** or **Cancel**. Refresh explicitly fetches the current default-branch HEAD for Owner review; it never starts Download or silently substitutes a revision.

Unknown licenses remain **License Review Required**. Local-only test synthesis is permitted for evaluation, but the model cannot enter the main Ready dropdown or an approved SHION voice workflow until Owner review is recorded. Source tokens are neither accepted by the UI nor logged.

Normal TTS deliberately sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` inside the Console process. An explicit Owner **Preview** or **Download** operation takes a shared environment lock, temporarily enables Hugging Face access for that operation only, keeps all cache paths on D drive, resets the Hub HTTP session, and restores the exact prior offline state afterward. User/Machine environment variables are never modified.

## Model actions

- **Refresh Models** performs hot discovery. The controller releases the current model and CUDA cache on model switch.
- **Test Voice** generates `「……聞こえる？ お兄さん♪」` and records latency, duration, and peak VRAM.
- **Disable / Enable** persists in `%SHION_DATA_ROOT%\data\voice\models.json`.
- **Remove Registration** excludes the registration without deleting weights. Physical deletion is never performed by the Manager.
- **Open Folder** opens only an allowlisted discovered directory under the D-drive model root.

After a model is Ready, tune it in the main Console, save a Candidate preset, listen, and only then explicitly approve a SHION preset. Adding a public model never makes it a canonical SHION voice.
