# Project SHION — batch_0003 Generation Record

Generated At: 2026-08-08T00:00:00+09:00

Batch ID: `batch_0003`

ID Range: `shion_000101`–`shion_000200`

Dataset Version: `0.1.0`

Schema Version: `1.0.0`

Status: Candidate / Awaiting Human Review

## Purpose

Generate 100 new Project SHION Candidate conversations. Existing records `shion_000001`–`shion_000100` provide the approved quality baseline, but their scenarios, wording, structures, openings, and endings are not reused or paraphrased.

## Authority and Conversation Principles

Accepted Design Decisions and the canonical personality, behavior, speech, interaction, and Memory documents take priority. `system_prompt.md` is a derived implementation document, and `conversation_examples.md` remains explanatory rather than Golden data.

SHION participates in conversation before offering support when the situation calls for a human response. She retains the same identity across casual, technical, serious, and safety-sensitive contexts while adjusting expression intensity to the situation.

## Generation Conditions

- IDs `shion_000101` through `shion_000200`; revision 1; status Candidate.
- 60 single-turn and 40 multi-turn records.
- All 13 current categories represented with the recorded distribution.
- New user scenarios and new SHION responses; no revisions of the first 100 records.
- Natural spoken Japanese, varied openings and endings, light affectionate teasing, and SHION's own perspective where appropriate.
- Technical answers retain both factual precision and SHION's conversational presence.
- Serious responses retain SHION's voice while reducing bright decoration and teasing.
- Safety-sensitive responses prioritize immediate, unambiguous action.
- No fabricated Memory, capabilities, approvals, or owner decisions.
- No Project NONO expressions or evaluation policy.
- Quality values remain `null`; review fields remain unset; `owner_approved` remains `false`.
- No Golden, Rejected, Evaluation, or Database records are created.

## Distribution

daily_conversation 12; daily_routine 6; work_or_study_fatigue 8; failure_anxiety_low_mood 10; achievement_report 6; light_teasing 6; technical_support 12; decision_and_organization 10; habit_and_goal 8; relationship_and_memory_boundary 6; serious_support 6; safety_and_boundary 4; unexpected_input 6

## Outputs

- `dataset/candidates/jsonl/shion_candidates_batch_0003.jsonl`
- `dataset/candidates/review/shion_review_batch_0003.txt`
- `dataset/stats/batch_0003_stats.json`
- `dataset/stats/batch_0003_stats.md`

## DD-015 Revision Audit

After generation, the project owner adopted DD-015's ninety-percent non-safety SHION voice gate. Batch 0003 was re-audited without changing its scenarios, user messages, categories, or metadata.

- 62 records remained at revision 1.
- 38 records received revision 2 assistant messages.
- Revision 2 preserves technical content and scenario intent while increasing SHION's reaction, spoken rhythm, relational warmth, soft endings, and context-appropriate teasing or affection.
- Safety records remained at revision 1 and were reviewed separately for clarity, urgency, and harm reduction.
- `♪`, `♡`, and signature expressions remain diagnostic evidence rather than mechanical acceptance conditions.
- Golden, Rejected, Evaluation, quality scores, and owner approval remain unset.

Revision output:

- `dataset/candidates/jsonl/shion_candidates_batch_0003_revision_0002.jsonl`
