# Project SHION Dataset

Dataset Version: 0.1.0

Schema Version: 1.0.0

Status: Candidate generation active; batch_0004 Owner approval synchronized

---

## Purpose

This dataset supports:

- a Japanese reference corpus for conversations consistent with SHION／紫苑
- regression review of System Prompts and conversation specifications
- possible future supervised fine-tuning candidates

It does not assume a specific model, runtime, or training execution.

## Authority

Operational policy is defined in [`../docs/development/dataset_strategy.md`](../docs/development/dataset_strategy.md).

Dataset content must follow:

- [`../docs/development/design_decisions.md`](../docs/development/design_decisions.md)
- [`../docs/character/personality.md`](../docs/character/personality.md)
- [`../docs/ai/behavior.md`](../docs/ai/behavior.md)
- [`../docs/character/speech.md`](../docs/character/speech.md)
- [`../docs/character/interaction.md`](../docs/character/interaction.md)

[`../docs/ai/system_prompt.md`](../docs/ai/system_prompt.md) is a derived implementation artifact. [`../docs/ai/conversation_examples.md`](../docs/ai/conversation_examples.md) is explanatory and is not a Golden Dataset or automated evaluation set.

## Directory Structure

| Path | Responsibility |
|---|---|
| `candidates/jsonl/` | Candidate JSONL revisions |
| `candidates/review/` | Human-readable review material |
| `golden/` | Owner-approved Golden records |
| `rejected/` | Preserved rejected revisions and reasons |
| `evaluation/` | Separately approved held-out evaluation artifacts |
| `database/` | Initial JSONL management database |
| `schemas/` | JSON Schema and controlled rejection codes |
| `prompts/` | Versioned batch-generation instructions |
| `stats/` | Generated distribution and quality audits |
| `BATCH_LOG.md` | Batch history |

## State Transitions

```text
candidate → needs_revision → candidate → golden
candidate → rejected
evaluation_candidate → held_out_review → evaluation
```

Automated checks must not promote a record to Golden. Golden status requires explicit project-owner approval.

## Golden and Evaluation

Golden records are approved reference-corpus entries and possible future training candidates.

Evaluation records are held-out comparison cases. They are not used for routine prompt adjustment or future training candidates. The same conversation text must not be copied between Golden and Evaluation.

Golden approval and Evaluation approval are separate operations.

## IDs and Revisions

- Conversation IDs use `shion_` followed by six digits.
- Once assigned, an ID is never reused, including after rejection.
- Human correction increments `revision` under the same ID.
- Earlier revisions remain preserved through lineage.

The planned first batch is `batch_0001`, covering `shion_000001` through `shion_000050`.

Every conversation must contain at least two messages, begin with `user`, end with `assistant`, and alternate roles. The JSON Schema validates the minimum length, allowed roles, and first role. A separate operational check must validate the final role and alternation before review or promotion.

Candidate, review, prompt-record, and statistics artifacts may exist while owner review is in progress. Golden, Rejected, and Evaluation status still require their separately defined review and approval steps.

For `batch_0003`, the Owner-edited Human Review TXT is preserved as the approval Source of Truth. Its conversations were synchronized one-way into new effective Candidate revisions, Golden records, and the management database. Earlier Candidate revisions remain as history.

For `batch_0004`, the Owner-approved attachment was preserved as `candidates/review/shion_review_batch_0004.txt` and registered one-way as `shion_000201`–`shion_000300`. All 100 are new IDs at formal revision 1. Review-time revision labels in the attachment are not repository revision history and did not alter the approved conversation text.

## Semantic Review Boundary

[`../tools/validate_dataset.py`](../tools/validate_dataset.py) validates JSON, Schema, identity, revision, lineage, review-state, rejection-code, and cross-set integrity rules. It does not determine whether a conversation passes DD-015 or DD-016.

Before owner review, generation and review must also apply:

- the Decoration Removal Test
- the Unsolicited Support Gate
- fact-grounded teasing review
- conversation-completion diversity review
- contextual helpfulness review

These require semantic human or model-assisted judgment. A structural Validator success must never be reported as proof that a Candidate is SHION-like or Golden-ready.
