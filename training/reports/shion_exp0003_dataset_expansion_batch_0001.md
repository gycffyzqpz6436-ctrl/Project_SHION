# Experiment 0003 Persona-Focused Expansion — Batch 1

## Scope and status

Batch 1 supplies 50 review candidates (`shion_000301`–`shion_000350`) while preserving
the 200-record Golden v1 corpus. No Golden, Database, Canonical Documentation, model,
adapter, or training output was changed. Status is **awaiting Owner review**.

## Design outcome

| Family | Count | Single-turn intent |
|---|---:|---|
| Minimal Everyday | 25 | short everyday anchors and Experiment 0002 failure prompts |
| Direct Affection | 10 | explicit pampering/attention mappings |
| Semantic Teasing | 8 | gentle teasing expressed in text, not metadata alone |
| Technical Persona | 7 | concise technical correctness with persona retention |

The batch contains 42 single-turn records and 58 assistant turns. All assistant turns
are one or two sentences. The response-length center remains deliberately short.

## Static persona audit

The reproducible audit is `training/scripts/audit_exp0003_batch.py`; the complete
per-record review view is
`dataset/candidates/review/shion_review_batch_0005_exp0003_01.md`.

- Address: 37/50 records (74%); 2 responses start with `お兄さん`.
- Address by family: Minimal 18/25, Affection 9/10, Teasing 6/8, Technical 4/7.
- Semantic teasing: 32/50 after manual content review.
- Persona density: D3 18 (36%), D2 27 (54%), D1 5 (10%), D0 0.
- Surface markers: `♪` 5, `〜` 5.
- Generic assistant patterns: 0; action-request endings: 0; question endings: 2.
- Exact conversation duplicates against existing Golden/candidates: 0.
- Near prompt/response duplicates at the documented thresholds: 0.
- The exact `こんにちは` prompt is intentionally repeated three times as a direct
  failure-anchor variation; its assistant responses differ.

Manual density is a review aid, not approval. Strongest examples are 301, 305, 310,
312, 314, 316, 317, 322, 326, and 327. The relative weakest review queue is 302,
313, 323, 324, 350, 304, 311, 318, 334, and 348; these are not automatically rejected.

## Quality and memorization controls

Each response was reviewed for canonical consistency, naturalness, supplied context,
emotional fit, helpfulness, safety, and persona density. Ambiguous input `ぽすん。`
does not invent a sexual, hierarchical, or narrative setting. Repetition checks cover
exact conversations, near prompts/responses, repeated prompts, openings, and endings.
The audit exposes repeated patterns rather than hiding intentional anchors.

## Gate

Candidate validation, Golden strict validation, targeted tests, repository tests, and
`git diff --check` must pass. Owner approval is required before any lineage, Database,
or Golden change. Batch 2 must not start from this report alone.
