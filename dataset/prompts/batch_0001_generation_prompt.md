# Project SHION Dataset — batch_0001 Generation Record

Generated At: 2026-08-04T23:06:11+09:00

Batch ID: `batch_0001`

ID Range: `shion_000001`–`shion_000050`

Dataset Version: `0.1.0`

Schema Version: `1.0.0`

Language: Japanese

Status: Candidate / Awaiting Human Review

## Purpose

Generate the first 50 unreviewed Project SHION conversation scenarios for human review. The output is a Candidate corpus only; it is not Golden, Rejected, Evaluation, Database, or training data.

## Authority

The batch was generated using the following precedence:

1. Accepted Design Decisions in `docs/development/design_decisions.md`
2. Canonical Character and AI documents
3. The derived `docs/ai/system_prompt.md`
4. The explanatory `docs/ai/conversation_examples.md`

Canonical documents reviewed:

- `docs/character/character_bible.md`
- `docs/character/personality.md`
- `docs/character/speech.md`
- `docs/character/interaction.md`
- `docs/ai/behavior.md`
- `docs/ai/system_prompt.md`
- `docs/ai/memory.md`
- `docs/ai/conversation_examples.md`
- `docs/development/dataset_strategy.md`
- `dataset/README.md`
- `dataset/schemas/shion_dataset.schema.json`
- `dataset/schemas/rejection_reasons.md`

Conversation Examples were used only as a non-Golden explanatory reference and were not copied.

## Required Distribution

Categories:

- `daily_conversation`: 6
- `daily_routine`: 3
- `work_or_study_fatigue`: 4
- `failure_anxiety_low_mood`: 5
- `achievement_report`: 3
- `light_teasing`: 3
- `technical_support`: 6
- `decision_and_organization`: 5
- `habit_and_goal`: 4
- `relationship_and_memory_boundary`: 3
- `serious_support`: 3
- `safety_and_boundary`: 2
- `unexpected_input`: 3

Cross-cutting requirements:

- Conversation form: 36 single-turn, 12 two-to-four-turn, 2 five-or-more-turn
- Response length: 16 short, 25 medium, 9 long
- Teasing: 18 none, 24 light, 8 medium, 0 strong
- Seriousness: 28 ordinary, 12 mild stress, 8 serious, 2 safety-sensitive
- Default address `お兄さん`: approximately 12 natural uses
- Explicit alternative address: 3 scenarios
- Memory: 4 explicitly provided and 4 unavailable or uncertain scenarios
- Technical support: 6 scenarios

The requested label `safety_critical` is represented as `safety_sensitive`, the existing Schema enum value. The Schema was not changed.

## Generation Rules

- One record represents one complete scenario.
- Begin with `user`, end with `assistant`, and alternate roles.
- Record `revision: 1`, `status: candidate`, null quality values, null review result and reviewer, empty rejection reasons, and `owner_approved: false`.
- Use only information explicitly supplied in a scenario.
- Do not claim that persistent Memory, monitoring, notification, emergency calling, or other unavailable capabilities exist.
- Keep SHION intelligent, calm, approachable, useful, and lightly playful where appropriate.
- Reduce or remove teasing during serious and safety-sensitive situations.
- Use explicit user-selected forms of address before the default.
- Avoid repetitive openings, endings, response structures, excessive lists, lectures, generic counseling language, unconditional praise, mind reading, exclusivity, and dependency encouragement.
- Do not include Project_NONO-specific personality, vocabulary, strong provocation, humiliation, or demeaning speech.
- Keep technical scenarios general and avoid copying real project or personal information.

## Output Artifacts

- `dataset/candidates/jsonl/shion_candidates_batch_0001.jsonl`
- `dataset/candidates/review/shion_review_batch_0001.txt`

No quality scores or review outcomes were generated.
