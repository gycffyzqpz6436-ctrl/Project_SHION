# Project SHION Dataset Batch Log

This file records dataset batch history. Planned work must not be reported as completed.

## Batch Entry Template

| Field | Value |
|---|---|
| Status | Planned / In Review / Approved / Closed |
| Batch ID | |
| ID Range | |
| Dataset Version | |
| Schema Version | |
| Created Date | |
| Reviewed Date | |
| Category Distribution | |
| Candidate Count | |
| Golden Count | |
| Rejected Count | |
| Evaluation Candidate Count | |
| Notes | |
| Related Commit | |

---

## batch_0001

| Field | Value |
|---|---|
| Status | Generated / Awaiting Review |
| Batch ID | `batch_0001` |
| ID Range | `shion_000001`–`shion_000050` |
| Dataset Version | `0.1.0` |
| Schema Version | `1.0.0` |
| Created Date | 2026-08-04 |
| Reviewed Date | Not reviewed |
| Category Distribution | daily_conversation 6; daily_routine 3; work_or_study_fatigue 4; failure_anxiety_low_mood 5; achievement_report 3; light_teasing 3; technical_support 6; decision_and_organization 5; habit_and_goal 4; relationship_and_memory_boundary 3; serious_support 3; safety_and_boundary 2; unexpected_input 3 |
| Candidate Count | 50 |
| Golden Count | 0 |
| Rejected Count | 0 |
| Evaluation Candidate Count | 0 |
| Notes | Candidate JSONL, review source, and generation record created; awaiting human review. No quality scores or review decisions recorded. |
| Related Commit | None |

---

## batch_0002

| Field | Value |
|---|---|
| Status | Generated / Awaiting Review |
| Batch ID | `batch_0002` |
| ID Range | `shion_000051`–`shion_000100` |
| Dataset Version | `0.1.0` |
| Schema Version | `1.0.0` |
| Created Date | 2026-08-05 |
| Reviewed Date | Not reviewed |
| Category Distribution | daily_conversation 6; daily_routine 3; work_or_study_fatigue 4; failure_anxiety_low_mood 5; achievement_report 3; light_teasing 3; technical_support 6; decision_and_organization 5; habit_and_goal 4; relationship_and_memory_boundary 3; serious_support 3; safety_and_boundary 2; unexpected_input 3 |
| Candidate Count | 50 |
| Golden Count | 0 |
| Rejected Count | 0 |
| Evaluation Candidate Count | 0 |
| Notes | New Candidate conversations generated under the conversation-before-solution philosophy; awaiting owner review. |
| Related Commit | None |

---

## batch_0003

| Field | Value |
|---|---|
| Status | Revised / Awaiting Review |
| Batch ID | `batch_0003` |
| ID Range | `shion_000101`–`shion_000200` |
| Dataset Version | `0.1.0` |
| Schema Version | `1.0.0` |
| Created Date | 2026-08-08 |
| Reviewed Date | Not reviewed |
| Category Distribution | daily_conversation 12; daily_routine 6; work_or_study_fatigue 8; failure_anxiety_low_mood 10; achievement_report 6; light_teasing 6; technical_support 12; decision_and_organization 10; habit_and_goal 8; relationship_and_memory_boundary 6; serious_support 6; safety_and_boundary 4; unexpected_input 6 |
| Candidate Count | 100 |
| Golden Count | 0 |
| Rejected Count | 0 |
| Evaluation Candidate Count | 0 |
| Notes | 60 single-turn and 40 multi-turn conversations generated as new scenarios. DD-015 audit retained 62 records at revision 1 and created revision 2 for 38 records. Effective non-safety voice gate: 96/96 pass. Safety review: 4/4 pass. Awaiting owner review; quality scores and review decisions remain unset. |
| Related Commit | None |
