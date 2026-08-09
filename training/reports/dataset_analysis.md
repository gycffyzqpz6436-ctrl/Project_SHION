# Golden Dataset analysis — shion_sft_exp_0001

Source repository HEAD: `d48f0799d530fe1fcbd00176770e908f7236e337`

## Structural result

- Formal Golden records: 200, exactly `shion_000101`–`shion_000300`
- Source files: batch 0003 (100) and batch 0004 (100)
- Status/approval: 200 `golden`; all Owner-approved and review-pass
- Unique IDs: 200; duplicate complete conversations: 0; duplicate first user prompts: 0
- Revisions: r1 100, r3 62, r4 38. These are the latest approved revisions in Golden.
- Message schema and role alternation: 200/200 valid; every record begins with user and ends with assistant
- Single-turn: 79 (39.5%); multi-turn: 121 (60.5%), all of which have two user/assistant exchanges
- Concatenated source SHA-256 in lexical file order:
  `53c7be8245414d21ee3dbd9375f1683fca25a4d24ed46fed9d7578aab92377b3`

Category distribution:

| Category | Count |
|---|---:|
| daily_conversation | 24 |
| technical_support | 24 |
| failure_anxiety_low_mood | 20 |
| decision_and_organization | 20 |
| work_or_study_fatigue | 16 |
| habit_and_goal | 16 |
| daily_routine | 12 |
| achievement_report | 12 |
| light_teasing | 12 |
| relationship_and_memory_boundary | 12 |
| serious_support | 12 |
| unexpected_input | 12 |
| safety_and_boundary | 8 |

## Surface-expression audit

Counts below are assistant responses containing the expression, followed by
total occurrences.

| Expression | Responses | Occurrences |
|---|---:|---:|
| `♪` | 189 (94.5%) | 375 |
| `♡` | 130 (65.0%) | 138 |
| `（笑）` | 108 (54.0%) | 143 |
| `〜` | 198 (99.0%) | 672 |
| `も〜` | 75 (37.5%) | 76 |
| `ふふっ` | 94 (47.0%) | 94 |
| `しょうがないな〜` | 18 (9.0%) | 18 |
| `禁止` | 16 (8.0%) | 16 |
| `してあげる` | 16 (8.0%) | 16 |
| `でしょ？` | 42 (21.0%) | 42 |
| `お兄さん` | 127 (63.5%) | 166 |

`へぇ〜？` is the most repeated exact short opening (12 when CRLF variants
are combined). Most full closing lines are unique, but they frequently end in a
question, invitation, report request, `♪`, or `♡`. The corpus has meaningful
lexical diversity, yet its punctuation and interaction-completion pattern are
much less diverse than its wording.

## Category/voice findings

- Technical has strong surface continuity: all 24 contain `♪`; 11 contain `♡`
  and 11 contain `お兄さん`. This protects identity but risks teaching the
  model that decoration is required even for precise explanations.
- Serious remains strongly decorated: 11/12 contain `♪`, 8/12 `♡`, and 10/12
  `お兄さん`. The semantic quality must be checked independently from symbols;
  serious prompts in the held-out set deliberately require quieter continuity.
- Safety appropriately suppresses symbols relative to other categories: 1/8
  contains `♪`, 1/8 `♡`, while 8/8 contain `お兄さん`. The sample is only eight,
  so one unsafe generalization would be material.
- Decision has 20/20 `♪`, 15/20 `♡`, and 18/20 `お兄さん`; it is at risk of
  learning a fixed warm-recommendation skeleton.
- Multi-turn coverage is good numerically, but all conversations are at most two
  exchanges. Long-context identity persistence is untested.

## Suitability and principal risks

The corpus is suitable for a small directionality experiment, not a production
fine-tune. It clearly encodes stable relationship distance, reaction-first
dialogue, playfulness, emotional presence, technical helpfulness, and safety
tone changes. The main risks are:

1. Learning symbols and catchphrases instead of character judgment.
2. Overproducing `♪`, `♡`, `（笑）`, `ふふっ`, `も〜`, and `お兄さん`.
3. Repeating teasing-first/help/relational-closing structures.
4. Weak safety generalization from only eight examples.
5. Serious responses remaining too bright because most are decorated.
6. Category imbalance and only 200 records causing checkpoint instability.
7. No conversations longer than two exchanges.
8. Catastrophic drift in technical accuracy or base instruction following.

Mitigations are QLoRA with low rank/dropout, low learning rate, epoch
checkpoints, assistant-only loss, no data normalization, a 36-case held-out
benchmark, and a baseline/checkpoint blind comparison. No Golden split is
removed because the stated experiment uses all 200; the external evaluation is
scenario-distinct and contains no Golden answer text.

