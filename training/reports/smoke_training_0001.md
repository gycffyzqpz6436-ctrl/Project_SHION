# Smoke Training result — shion_sft_exp_0001

Executed 2026-08-09 JST with only the approved Model A command.

## Result

- Exit code: 0
- Records: 4 (`shion_000101`–`shion_000104`)
- Record lengths: 630, 614, 619, 630 tokens
- Optimizer steps: 2
- Training runtime: 7.525 seconds
- End-to-end runtime including model load/save: 22.080 seconds
- Mean step time: 3.763 seconds
- Trainer aggregate loss: 3.449
- Forward-only mean loss before adapter: 3.4496089816
- Forward-only mean loss after reloaded adapter: 3.3849978447
- All recorded losses finite; no NaN or Inf
- Peak observed VRAM: 11,791 MiB / 12,227 MiB
- Maximum GPU temperature: 54 C
- Maximum GPU power: 194.31 W
- Maximum GPU utilization: 99%

## Save and reload

Saved:

- `D:/AI/Project_SHION/training_output/shion_sft_exp_0001/smoke/checkpoint-1`
- `D:/AI/Project_SHION/training_output/shion_sft_exp_0001/smoke/checkpoint-2`
- `D:/AI/Project_SHION/training_output/shion_sft_exp_0001/smoke/final_adapter`

Checkpoint-2 and final-adapter safetensor SHA-256 are identical:
`9d6b574f82642c31775c3972d37f73f9cea8474cdd7f0904b80e484f30a55686`.

Reload passed with rank 8, alpha 16, dropout 0.10, 272 language-attention
LoRA modules, and zero vision-tower targets.

## Warnings and recommendation

- Triton is absent; only PyTorch FLOP counting is unavailable. SDPA training
  completed normally.
- Transformers warns that `warmup_ratio` is deprecated; use an explicit
  `warmup_steps` value after total-step calculation.
- `logging_steps=5` did not retain per-step loss for a two-step smoke. Use 1 for
  the next diagnostic run.
- Telemetry sampled once per second; sub-second spikes may be missed.
- Only ~436 MiB VRAM remained at the observed peak. The corpus maximum is 835
  tokens, while this smoke maximum was 630 and 155/200 records are longer.
  Before Full Training, run one separately approved step containing a longest
  record. If it does not fit, reduce max sequence length to 896 (still above the
  measured maximum) and close other GPU applications.

Golden, database, and canonical documentation are unchanged. Training output is
external to the repository and no output/model file is tracked.

