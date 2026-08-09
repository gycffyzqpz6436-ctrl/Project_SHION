# Gemma 4 Owner Manual Chat: Long Generation Review

Date: 2026-08-09

## Scope

This change applies only to `gemma4_12b_it_manual` and
`gemma4_12b_heretic_ja_v2_manual`. It does not run model inference, change model
weights, or alter SHION canonical data or Experiment 0001.

## Effective limits

- Before: both Gemma aliases overrode the shared setting with
  `max_new_tokens: 128`.
- After: both Gemma aliases use a hard safety ceiling of 4096 new tokens.
- The ceiling is not a requested response length. Normal EOS termination remains
  active, including Gemma EOS IDs `[1, 106, 50]`.
- At runtime, the effective maximum is
  `min(4096, model_context_limit - rendered_input_tokens)`.
- Conversation history is never silently truncated. If no token remains, the
  request fails before generation and the Owner must start a new chat.

Local offline config/tokenizer inspection found a 262144-token total context and
a 1024-token sliding-attention window for both models. The prior helper incorrectly
treated the sliding window as the total context. Sliding-window size is now used
only as a fallback when no total context value is available.

## Prompt and stopping behavior

The Neutral Conversation prompt still asks for brief replies to short casual
messages, and now explicitly permits the requested detail and length when the
Owner asks for a long or detailed answer.

No repetition guard is configured for either Gemma registry entry. Therefore the
runtime does not add a custom repetition stopping criterion to ordinary Gemma
responses. The model-specific EOS configuration remains the normal early-stop
mechanism. Non-thinking chat-template options remain unchanged.

## Static and mock verification

- Verified 4096 ceiling for both Gemma aliases and unchanged settings for other
  model aliases.
- Verified remaining-context clamping and rejection only when no context remains.
- Mocked a one-token early-EOS response under a larger ceiling.
- Verified the generate call receives Gemma EOS IDs `[1, 106, 50]`.
- Verified the 262144 total context is not reduced to the 1024 sliding window.

Actual long generation remains an Owner manual test.
