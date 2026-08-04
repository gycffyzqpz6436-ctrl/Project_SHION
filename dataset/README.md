# Project SHION Dataset

Dataset Version: 0.1.0

Schema Version: 1.0.0

Status: Scaffold only; no conversation records exist

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

No Candidate, Golden, Rejected, Evaluation, review, database, or statistics records currently exist.
