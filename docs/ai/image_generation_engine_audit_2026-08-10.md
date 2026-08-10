# SHION 2D Anime Image Generation Engine Audit

Date: 2026-08-10 (Asia/Tokyo)

Scope: research, pre-download security/license review, one-model installation, and two bounded offline tests

Status: engine-only experimental runtime; the SHION Web UI remains unchanged

## Decision

The first candidate is **Animagine XL 4.0 Opt** from `cagliostrolab/animagine-xl-4.0`.
It combines strong anime output, a clear SDXL parent, standard Diffusers compatibility,
an established tag/LoRA ecosystem, and the CreativeML Open RAIL++-M license. The Opt
checkpoint is preferred to the normal checkpoint because the developer states that it
adds stability, anatomy/proportion accuracy, lower noise, and improved saturation and
color accuracy. This is a model-card claim, not proof of perfect hands; manual tests are
still required.

Top 3:

1. Animagine XL 4.0 Opt — first installation candidate; clearest overall fit and license.
2. Illustrious XL v1.1 — strong natural-language/character knowledge, but thin lineage and
   licensing documentation in the actual v1.1 repository reduce confidence.
3. NoobAI XL 1.1 — potentially excellent character/tag knowledge, but its added license
   terms are unsuitable for a possibly public or commercial SHION release.

This is an engineering audit, not legal advice. A public/commercial release should receive
qualified license review, especially for training-data and output-rights questions that a
model license cannot settle.

## Candidate comparison

Ratings are relative engineering judgments: 5 excellent, 1 poor, `?` not adequately
verified. Quality ratings combine official model-card claims, ecosystem evidence, and the
two local tests only for the selected model. “Hands” is deliberately conservative.

| Candidate (exact repository) | Anime | Character / face | Hands / anatomy | Pose | Prompt following | Unassisted consistency | Style range | Prompt mode | LoRA ecosystem | Reference / Control | RTX 5070 12 GB | License / distribution |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|
| `cagliostrolab/animagine-xl-4.0` Opt | 5 | 5 / 5 | 3 / 4 | 3 | 4 tags, 2 prose | 2 | 4 | Danbooru tags; hybrid after translation | 4 | SDXL adapters: 4 | Yes, FP16 1024² | Open RAIL++-M; safe files; selected |
| `OnomaAIResearch/Illustrious-XL-v1.1` | 5 | 5 / 5 | 3 / 4 | 4 | 4 prose, 5 tags | 2 | 5 | Hybrid; more prose-focused than v1.0 | 5 | Illustrious/SDXL: 4 | Yes, FP16 | SDXL license link only; lineage documentation gap |
| `Laxhar/noobai-XL-1.1` | 5 | 5 / 5 | 3 / 4 | 4 | 2 prose, 5 tags | 2 | 5 | Native Danbooru/e621 tags | 5 | Illustrious/SDXL: 4 | Yes, FP16 | Fair-AI plus restrictive additions; cautious/reject formal use |
| `OnomaAIResearch/Illustrious-XL-v2.0` | 5 | 5 / 5 | 4 / 4 | 4 | 4 hybrid | 2 | 5 | Hybrid | 4 | Illustrious/SDXL: 4 | Yes | Open RAIL-M metadata; sparse card; not chosen over requested v1.1 audit |
| `KBlueLeaf/Kohaku-XL-Zeta` | 4 | 4 / 4 | 3 / 4 | 4 | 2 prose, 5 tags | 2 | 5 | Danbooru tags | 4 | SDXL: 4 | Yes; download safetensors only | Fair-AI; repo also contains `.bin` duplicates, so filtered download required |
| `KBlueLeaf/Kohaku-XL-Epsilon-rev3` | 4 | 4 / 4 | 3 / 3 | 3 | 2 prose, 5 tags | 2 | 5 | Danbooru tags | 4 | SDXL: 4 | Yes | Fair-AI; repo also contains pickle `.bin`; not top 3 |
| `cagliostrolab/animagine-xl-3.1` | 4 | 4 / 4 | 3 / 3 | 3 | 2 prose, 5 tags | 2 | 4 | Danbooru tags | 5 | SDXL: 4 | Yes | Open RAIL++-M; superseded by 4.0 Opt |
| `6chan/Pony-Diffusion-V6-XL` | 4 | 4 / 4 | 3 / 4 | 4 | 2 prose, 5 score-tags | 2 | 5 | Pony score/tag syntax | 5 | Pony/SDXL: 4 | Yes | Official API returned 401 during audit; gated/unavailable, reject download |
| `Remilistrasza/CounterfeitXL` | 4 | 4 / 4 | 2 / 3 | 3 | 2 prose, 4 tags | 2 | 4 | Tag/hybrid | 3 | SDXL: 3 | Yes | Official API returned 401 during audit; exact files not auditable, reject |

All SDXL-class candidates normally occupy about 6.9–7.1 GB as a single FP16 checkpoint.
At 1024² and batch 1, inference is realistic on 12 GB, but peak reservations can approach
the entire device. Speed depends on scheduler, attention backend, offload, and driver.

## Natural language and prompt strategy

Animagine 4.0 explicitly says natural-language input may be ineffective and documents a
tag order. It should not receive raw Japanese. The intended path is:

```text
Japanese user request
  -> Gemma 4 intent interpretation
  -> validated SHION Visual Spec (model neutral)
  -> model-specific Prompt Builder (short, ordered tags)
  -> Image Tool Interface
  -> isolated Diffusers runtime
```

Illustrious v1.1 is the best of the required candidates for direct prose/hybrid prompting.
NoobAI is tag-native. For SHION, a hybrid builder should preserve identity, adult/safety,
pose and clothing fields, then add model quality tags. SDXL CLIP has a 77-token window;
the initial experiment proved that an overlong prompt silently truncates trailing controls.
The checked-in builder now enforces a conservative character budget and reserves quality
tags. A later tokenizer-aware builder should count both SDXL tokenizers exactly.

## Top-3 security review before download

### Animagine XL 4.0 / Opt — accepted

- Repository/owner/developer: `cagliostrolab/animagine-xl-4.0`; Cagliostro Research Lab.
- Fixed revision: `2b7c1b397761bf5bd3cc42e5b39ec99314a75a96`; ungated.
- Parent/lineage: fine-tuned from `stabilityai/stable-diffusion-xl-base-1.0`, retrained
  with an 8.4M-image anime dataset; Opt is an additional refinement of 4.0.
- Files at the revision: README, model index/config/tokenizers, FP16 safetensors components,
  `animagine-xl-4.0.safetensors`, and `animagine-xl-4.0-opt.safetensors`; no CKPT, pickle,
  executable, install script, custom Python, `auto_map`, or unusual binary was found.
- The card demonstrates `custom_pipeline="lpw_stable_diffusion_xl"`. That path can retrieve
  third-party/community code and is **not accepted**. SHION uses the stock
  `StableDiffusionXLPipeline`, `local_files_only=True`, and no remote code.
- Runtime dependencies are standard PyTorch, Diffusers, Transformers, Accelerate,
  Safetensors, Pillow and Hugging Face Hub. No external downloader is used at runtime.

### Illustrious XL v1.1 — conditional

- Repository/owner: `OnomaAIResearch/Illustrious-XL-v1.1`; OnomaAI Research.
- Audited revision: `8d966ec810874502d56a22ec9130dab6ef74c5ff`; ungated.
- Three files only: `.gitattributes`, README, and one 6,938,040,728-byte safetensors.
  No code, executable, pickle, custom pipeline, or remote-code requirement.
- Card says v1.1 continues v1.0 and links the SDXL license, but does not provide an in-repo
  license file or a complete v1.0-to-parent training lineage. The early public lineage is
  SDXL -> Kohaku XL Beta 5 -> Illustrious early v0; the exact path through closed v1.0 to
  v1.1 is insufficiently documented. This prevents first-place security/license confidence.

### NoobAI XL 1.1 — technical files pass, formal adoption rejected

- Primary distribution: `Laxhar/noobai-XL-1.1`, owner Laxhar Dream Lab/LAXMAYDAY.
- Audited revision: `814a274af2b8097c0828819d561ec74c7d0c6cea`; ungated.
- Parent/lineage: NoobAI XL 1.1 -> `Laxhar/noobai-XL-1.0` -> Illustrious early release
  -> Kohaku XL Beta 5 -> SDXL. It is trained with native Danbooru and e621 tags.
- Files are README, Diffusers JSON/tokenizers, and safetensors only; no CKPT/pickle/code,
  executable, installer, custom pipeline, `auto_map`, or remote-code requirement found.
- Technical distribution passes the stated safetensors/no-code rule. License risk fails the
  formal-product threshold.

## License findings

### Animagine / SDXL Open RAIL++-M

The repository states that it adopts the original CreativeML Open RAIL++-M without added
restrictions. Local/private use, commercial use, modification, derivative models, LoRA and
redistribution are permitted subject to the use restrictions and distribution duties.
Distributions must carry the license/use restrictions and relevant notices; modifications
must be identified. The license says the licensor claims no rights in outputs, while output
copyright and training-data rights remain jurisdiction/fact dependent. LoRAs and fine-tunes
are derivatives and must preserve at least the original use restrictions.

### Illustrious v1.1

The v1.1 metadata/card links directly to the SDXL Open RAIL++-M license. Therefore local,
commercial, LoRA, fine-tune and redistribution use appear possible under the same duties.
However, the missing local LICENSE and incomplete v1.0 lineage mean SHION should preserve
the exact downloaded card/license evidence and seek review before public redistribution.

### NoobAI 1.1 / Fair-AI plus additions

The base Fair-AI 1.0-SD is copyleft-like and requires corresponding source/license when
distributing; its project description also describes network-service source disclosure.
NoobAI 1.1 adds stricter terms that bind the model and variants:

- private/local use is possible if all use restrictions are obeyed;
- **all commercialization is prohibited**, expressly including model-generated products;
- derivative/fine-tuned/merged models and LoRAs must be open sourced;
- synthesis formulas, prompts, workflows and other work details must be shared;
- redistribution must carry inherited/additional terms and corresponding source duties;
- generated-image sharing is permitted, but the added commercial ban still applies.

Consequently a private experiment is possible, but a future public SHION, hosted service,
closed character LoRA, paid product, or commercial generated-image workflow can trigger
serious incompatibility. NoobAI is not the formal first candidate despite its quality.

Primary sources: the three Hugging Face model cards/file trees, the
[official SDXL license](https://github.com/Stability-AI/generative-models/blob/main/model_licenses/LICENSE-SDXL1.0),
and the [Fair-AI 1.0-SD text](https://freedevproject.org/faipl-1.0-sd/).

## Installed artifact and integrity

- Exact repository: `cagliostrolab/animagine-xl-4.0`
- Revision: `2b7c1b397761bf5bd3cc42e5b39ec99314a75a96`
- Weight: `animagine-xl-4.0-opt.safetensors`
- Weight size: 6,938,350,040 bytes (6.46 GiB)
- SHA-256: `6327eca98bfb6538dd7a4edce22484a1bbc57a8cff6b11d075d40da1afb847ac`
- HF blob ID: `712da5255f961c3e0c10894af0c042fbacb7ea98`
- HF LFS metadata: size and SHA-256 exactly match; pointer size 135 bytes.
- Local directory: `D:\AI\Project_SHION\models\image\animagine-xl-4.0-opt`
- D: before/after: 128,719,351,808 / 119,974,875,136 free bytes. More than 80 GiB remains.
- Only the selected Opt weight and required local Diffusers configuration/components were
  downloaded. The normal 4.0 checkpoint was intentionally excluded.

## Runtime and measured tests

Dedicated environment: `app/tools/image_generation/.venv` (Git-ignored), Python 3.10.6,
PyTorch 2.11.0+cu128, Diffusers 0.39.0, Transformers 5.15.0, Accelerate 1.14.0.
The conversation `training/.venv` and system Python were not modified.

Backend decision:

| Backend | Integration | Complex controls | Footprint / decision |
|---|---|---|---|
| Diffusers | Best direct typed Python API; version-pin and testable | Good; explicit assembly required | Selected now |
| ComfyUI | API/workflows are flexible | Best visual graphs for multi-ControlNet/reference chains | Future optional sidecar, not installed |
| Forge | WebUI/extension-centric | Broad community support | Not installed; less clean application boundary |
| A1111 | Mature extensions | Broad but extension/version coupling | Not installed; largest legacy coupling |

Both tests used 1024x1024, 28 steps, Euler Ancestral, CFG 5.0, FP16, batch 1, and
`local_files_only=True` with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and
`DIFFUSERS_OFFLINE=1`. No custom pipeline and no `trust_remote_code` were used.

| Test | Seed | Load | Generation | Torch peak allocated / reserved | GPU used after | Temp / power after | Output size |
|---|---:|---:|---:|---:|---:|---:|---:|
| standing | 20260810 | 3.952 s | 11.051 s | 8.96 / 11.31 GiB | 11,867 / 12,227 MiB | 49 C / 63.77 W | 1,045,597 B |
| three-quarter/wave request | 20260811 | 3.904 s | 10.592 s | 8.96 / 11.31 GiB | 11,765 / 12,227 MiB | 47 C / 61.96 W | 1,007,605 B |

Artifacts (Git-excluded):

- `D:\AI\Project_SHION\image_output\experimental\animagine-xl-4.0-opt-test-01.png`
- `D:\AI\Project_SHION\image_output\experimental\animagine-xl-4.0-opt-test-01.json`
- `D:\AI\Project_SHION\image_output\experimental\animagine-xl-4.0-opt-test-02.png`
- `D:\AI\Project_SHION\image_output\experimental\animagine-xl-4.0-opt-test-02.json`

Manual observation: both are clean anime illustrations with attractive faces and plausible
overall anatomy. The first image's overlapping small hands make finger count uncertain. The
second shows fingers but does not strongly follow the requested wave. Across seeds, hair
length/style, face, clothing design/color and background changed materially. Text-only
descriptions are not sufficient for SHION identity consistency.

## Character consistency and controls

Because the model retains standard SDXL architecture, Diffusers supports img2img and
inpainting pipelines and can compose SDXL ControlNet models for OpenPose, depth and lineart.
SDXL IP-Adapter/reference-image workflows are feasible, but adapter provenance and base
compatibility must be audited independently. A ControlNet does not automatically preserve a
face; use layers deliberately:

1. Character LoRA for identity/style priors.
2. IP-Adapter/FaceID or a separately approved reference adapter for facial appearance.
3. OpenPose ControlNet for pose, optionally depth/lineart for geometry.
4. Inpainting with masks for “change clothes only” while protecting face/hair/background.
5. Fixed Visual Spec, seeds, scheduler and color palette metadata for reproducibility.

ControlNet plus IP-Adapter at 1024² may exceed 12 GB without CPU offload, attention slicing,
lower resolution, or sequential loading. Each adapter repository needs the same no-code,
safetensors, revision, license and hash audit as the base model.

## Character LoRA feasibility

Animagine 4.0 Opt is an SDXL checkpoint and can train a character LoRA with common SDXL
trainers. A conservative starting experiment is 25–50 curated images (15 is a bare minimum;
50–100 improves pose/outfit coverage), 1024-resolution aspect buckets, and captions that use
a unique character token plus Danbooru tags. Keep immutable identity traits in every caption;
caption clothing/pose/background so they do not become fused to the identity.

Start with rank/dimension 16 or 32 (alpha 8–16), UNet LoRA first, FP16/BF16, gradient
checkpointing, batch 1, 8-bit optimizer, and cached latents. RTX 5070 12 GB training is
possible but tight; text-encoder training may require offload or should be disabled initially.
Expected time is roughly 1–4 hours for a small 1,500–4,000-step experiment, highly dependent
on caching and optimizer. Train against the exact Opt checkpoint/revision; an Illustrious,
NoobAI, Pony, or plain-SDXL LoRA is not assumed interchangeable. This audit did not train one.

## GPU decision

No GPU purchase is necessary for single-image SDXL generation. The 5070 achieved about
10.6–11.1 seconds at the requested settings. Basic LoRA is feasible with memory-saving
settings. A single ControlNet or reference adapter is plausible with offload/tuning; stacked
reference + multiple ControlNets at 1024² will be constrained.

A second 5070 does not become a transparent 24 GB pool: ordinary inference/training keeps
separate 12 GB address spaces unless the application explicitly shards modules, and most
SDXL community workflows do not benefit enough to justify it. If future needs justify an
upgrade, useful single-device targets are 16 GB for more comfortable adapters/basic LoRA,
24 GB for multi-control workflows and easier text-encoder LoRA training, and 32–48 GB for
larger batches/full fine-tunes. Present judgment: **additional GPU unnecessary now; 24 GB+
single-device VRAM may be useful later**, based on measured workflow pressure.

## Security boundary and next implementation

`app/tools/image_generation` currently contains only the neutral spec, prompt builder,
audited registry, download/integrity utility and experimental runtime. The default tool
registry still disables `image_generation`; nothing is connected to the Web UI.

The eventual runtime must execute as an isolated process/service with a narrow JSON request
and response schema. The orchestrator may pass validated visual fields and approved reference
paths, never a Python model object. The runtime receives read-only model paths and a dedicated
output directory, has networking disabled, cannot shell out except controlled telemetry,
uses an allowlisted model revision, and cannot access arbitrary filesystem paths. Model
outputs return as artifact metadata to the orchestrator and then the SHION Web UI.

## Owner commands

Run unit tests:

```powershell
training\.venv\Scripts\python.exe -m pytest tests/test_image_generation_boundary.py
```

Inspect the two experimental images:

```powershell
explorer D:\AI\Project_SHION\image_output\experimental
```

Re-run one bounded offline test only after consciously choosing to create another artifact:

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:DIFFUSERS_OFFLINE='1'
app\tools\image_generation\.venv\Scripts\python.exe -m app.tools.image_generation.generate_experimental --model-dir D:\AI\Project_SHION\models\image\animagine-xl-4.0-opt --output D:\AI\Project_SHION\image_output\experimental\owner-manual-test.png
```

Do not begin LoRA training until Owner Manual Test accepts face, hands, pose response and
style. Before any public/commercial release, re-audit the pinned model license and every
adapter/LoRA license.

## Repository validation

- Full suite: 50 passed, 1 skipped (51 collected).
- New image boundary tests: 3 passed.
- Source-only `py_compile`: passed.
- `git diff --check`: passed (Git emitted only the normal Windows LF/CRLF notice).
- Image venv, model weights, Hugging Face cache and generated artifacts are ignored or
  located outside the repository.
