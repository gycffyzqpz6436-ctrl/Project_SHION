# Experiment 0002 Web Integration Gate

Date: 2026-08-22
Gate: static integration only; no model load, generation, evaluation, or training

## Result

The completed Experiment 0002 final adapter is exposed through the server-side
allowlisted alias `shion_gemma4_exp0002_manual`. The alias uses the same official
`Gemma4UnifiedForCausalLM` text-only class as training and adapter reload, while
preserving the Official Gemma local base, revision, non-thinking chat-template
option, and generation policy. It adds an immutable LoRA binding; it does not
merge or rewrite the base checkpoint. The separate Official Gemma and Heretic
aliases remain `AutoModelForMultimodalLM` for their existing multimodal runtime.

Static adapter gate: **PASS**

- Training manifest: PASS / full / 75 completed optimizer steps
- Base: `google/gemma-4-12b-it`
- Revision: `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`
- Records / epochs: 200 / 3
- LoRA: r8, alpha16, dropout0.1, q/k/v/o, expected targets 184
- `adapter_model.safetensors` SHA-256:
  `5ab2fbd566f65f9d1aab2030663efc4b1f9660b8293ada4505e259c158dce11e`
- `adapter_config.json` SHA-256:
  `640f5fadcd53752f825806c97c987cbaa0db6ffb0c4a00a14e312645247eab1a`

## Runtime safety contract

Before GPU load, the runtime requires the fixed adapter directory, safetensors,
config, and sibling manifest, then checks base path, model ID, revision,
experiment ID, status, dataset size, epochs, LoRA settings, and manifest path.
After PEFT attachment it requires an active adapter and exactly 184 LoRA targets.
Any mismatch fails model loading; there is no Official-base fallback. PEFT uses
the existing local base with `local_files_only=True` and the base runtime retains
`trust_remote_code=False`.

The Browser receives only the alias and public provenance. The adapter path is
not part of the public model registry response and cannot be supplied by the
Browser model-switch endpoint.

## Validation

- Fixed artifact/manifest validation: PASS
- Base runtime/generation equivalence: PASS
- Targeted runtime tests: 21 PASS
- Repository suite: 170 PASS, 10 subtests PASS (14 upstream deprecation warnings)
- Golden strict validation: 14 PASS, 10 subtests PASS
- Python syntax and registry JSON: PASS
- `git diff --check`: PASS
- JavaScript parser check: UNVERIFIED (`node` is not installed in this environment)
- GPU load / adapter attach / conversation generation: deliberately NOT RUN;
  reserved for Owner manual evaluation
