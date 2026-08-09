# Impish Nemo 12B generation stabilization

Date: 2026-08-09

## Diagnosis

The pinned local tokenizer uses ChatML with `<|im_end|>` as EOS (token ID 2), and
minimal mode renders a user turn followed by `<|im_start|>assistant`. The local
model config, tokenizer config, special-token map, and generation config agree on
EOS. The malformed output was therefore not caused by a missing assistant marker
or mismatched EOS token.

The shared defaults (`temperature: 0.3`, `repetition_penalty: 1.05`, and
`max_new_tokens: 512`) were too deterministic and too permissive once this RP
fine-tune entered a repeated phrase loop. Runtime generation also did not pass EOS
explicitly and had no last-resort repetition stop.

## Model-scoped remedy

Only `impish_nemo12b_experimental` receives these runtime overrides:

- temperature: 0.7
- top-p: 0.9
- top-k: 50
- repetition penalty: 1.10
- maximum new tokens: 128

The runtime now passes the tokenizer EOS and PAD IDs explicitly and enables the
inference KV cache. A conservative guard stops only a generated token block of
4–32 tokens repeated consecutively three times. It does not ban ordinary repeated
words or affect either official model.

This is a runtime stabilization, not a finding that the model's Japanese or SHION
fitness is acceptable. Final conversational quality remains an Owner manual review.

## One-prompt runtime check

The authorized `こんにちは` / minimal-mode / 64-token check was started once with
offline loading, `local_files_only=True`, `trust_remote_code=False`, and 4-bit NF4.
The process did not reach generation: local weight loading reached 283/363 entries
but exceeded the 240-second command limit. Its orphaned child process was stopped
and GPU memory returned from 9,087 MiB to 642 MiB. No response was produced, so
runtime output quality and EOS termination are not claimed as verified here.
