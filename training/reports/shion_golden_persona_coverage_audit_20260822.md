# SHION Golden Persona Coverage Audit — 2026-08-22

## Executive conclusion

Golden `shion_000101`–`shion_000300` is internally consistent, casual, and almost
free of generic help-desk phrases. Its main weakness is **coverage geometry**, not
the presence of polite Assistant prose. It teaches many medium/long, richly styled,
context-specific exchanges, but almost no minimal everyday anchors. There are no
training inputs for `こんにちは`, `おはよ`, `おやすみ`, `今日何もしなかった`,
`甘やかして`, `仕事行きたくない`, `帰ってきた`, `ジム行ってきた`, or
`ちょっと話したい`. Only one of 321 Assistant turns is a one-sentence answer.

This explains the Owner observations better than a generic-phrase contamination
hypothesis: Gemma's strong greeting/helpfulness prior receives no direct competing
example, while affection is learned mostly inside elaborate scenarios rather than
as a short direct reaction. Experiment 0003 should add 200 high-density, deliberately
short and distribution-targeted records, for a proposed Golden total of **400**.
The existing 200 records were not modified.

## Scope and methodology

- Read-only sources: both `dataset/golden/*.jsonl`, database lineage, and Canonical
  `speech.md`, `personality.md`, and `interaction.md`.
- Exact scope: 200 contiguous IDs, `shion_000101` through `shion_000300`.
- Database check: every Golden ID/revision/status has a matching database revision.
- Unit: record-level counts concatenate all Assistant turns; turn-level length
  statistics treat the 321 individual Assistant messages separately.
- Classification: metadata establishes scenario/category intent; deterministic
  content rules check realized address, teasing, affection, care, style, and phrases.
- Manual validation: 40 stratified records were read across casual, technical,
  relationship, serious, safety, high-score, and low-score strata. Keyword results
  were corrected in interpretation—for example, the sole `遠慮なく` hit is natural
  character dialogue, not generic Assistant bias.
- Persona Density deliberately does not award points merely for `お兄さん`, `♪`,
  `♡`, or a signature expression. It uses semantic teasing, personal perspective,
  care, empathy, affection, humor, and spoken rhythm, following Canonical's
  “remove the decoration and reassess” rule.

The reproducible implementation is `training/scripts/audit_persona_coverage.py`.
Its output is diagnostic, not permission to rewrite the Dataset.

## Source integrity and category balance

| Item | Result |
|---|---:|
| Golden records | 200 |
| ID range | 000101–000300, contiguous |
| Database lineage match | 200/200 |
| Single-turn records | 79 (39.5%) |
| Multi-turn records | 121 (60.5%) |

Formal source categories:

| Category | Count | Category | Count |
|---|---:|---|---:|
| daily_conversation | 24 | daily_routine | 12 |
| work_or_study_fatigue | 16 | failure_anxiety_low_mood | 20 |
| achievement_report | 12 | light_teasing | 12 |
| technical_support | 24 | decision_and_organization | 20 |
| habit_and_goal | 16 | relationship_and_memory_boundary | 12 |
| serious_support | 12 | safety_and_boundary | 8 |
| unexpected_input | 12 | | |

For the requested broad view, the exclusive source-category partition is Casual
88, Emotional Support 20, Technical 24, Serious 12, Safety 8, Other 48. Affection
and teasing are behavioral overlays rather than mutually exclusive categories.

## Persona-element coverage

| Element | Records | Rate | Interpretation |
|---|---:|---:|---|
| お兄さん | 127 | 63.5% | Moderate overall; weak in key casual/technical anchors |
| Semantic light teasing | 65 | 32.5% | Far below 141 `teasing_light` metadata tags |
| Direct pampering | 10 | 5.0% | Sparse; no direct user request “甘やかして” |
| Kindness/care/affection | 173 | 86.5% | Broad, but frequently embedded in long responses |
| Intimate chat | 27 | 13.5% | Limited |
| Casual-category conversation | 88 | 44.0% | Only 24 are short, single-turn casual examples |
| Encouragement | 49 | 24.5% | Present |
| Empathy | 46 | 23.0% | Present, often long-form |
| Comforting | 47 | 23.5% | Distinct from generic therapy in reviewed samples |
| Explicit affection | 136 | 68.0% | High because `♡`/affection wording is common |
| Physical-affection wording | 1 | 0.5% | Almost absent |
| Emotional closeness | 173 | 86.5% | High surface/relational signal |
| Humor | 150 | 75.0% | Very frequent; includes laughs |
| Playful response | 194 | 97.0% | Near-universal surface playfulness |
| Caretaking | 112 | 56.0% | Strong, sometimes turns into assigned action |
| Cool/calm problem handling | 38 | 19.0% | Concentrated in technical/safety |
| Intellectual/analytical | 64 | 32.0% | Technical plus decision/analysis language |
| Technical Help | 24 | 12.0% | Complete source category |
| Boundary/refusal context | 20 | 10.0% | Relationship 12 + safety 8 |

The large gap between 141 intended teasing tags (70.5%) and 65 semantic teasing
matches (32.5%) matters. Many tagged examples use `♪`, `〜`, a question, or a soft
ending but do not actually tease. Surface style is abundant; behavioral teasing is
not equally abundant.

## Address-marker audit

`お兄さん` appears in 127 records (63.5%), 166 times total. Thirty-five records
use it more than once. Position counts are: start 0, middle 161, end 5. Context:

| Context | Address records | Context total | Rate |
|---|---:|---:|---:|
| Casual | 48 | 88 | 54.5% |
| Technical | 11 | 24 | 45.8% |
| Serious (metadata seriousness) | 12 | 16 | 75.0% |
| Safety | 8 | 8 | 100.0% |

The overall rate is not low, but its distribution is inverted relative to the
Canonical guidance: familiar ordinary/technical examples need stronger natural
anchoring, while safety uses the address universally. The marker is nearly always
embedded mid-response and never opens a turn, so a model facing a bare greeting has
little evidence to immediately choose the relationship. Batch-level address records
also rise from 21/50 in IDs 101–150 to 41/50 in 251–300, making coverage uneven.

## Assistant bias and distance

Mechanical search found only `遠慮なく` in `shion_000279`. Manual review shows it
means “if I misread your name again, correct me without hesitation” inside highly
personal dialogue. It is **not** generic Assistant bias. The other searched families
(`何かお手伝い`, `お手伝いできます`, `何かできること`, `ご質問`, `ご相談`,
`サポート`, `お役に立て`, `いかがでしょうか`, `してみてください`, and
`おすすめします`) occur zero times.

Style classification: Casual 200, Mixed 0, Polite 0, Strongly polite 0. Raw polite
markers total `です` 3, `ます` 1, `ください` 0, `でしょう` 0, `ございます` 0.
Therefore Experiment 0002's polite greeting is inherited Base behavior, not a
phrase distribution copied from Golden.

## Response length and ordinary-chat coverage

| Character metric | Per record | Per Assistant turn |
|---|---:|---:|
| min | 40 | 15 |
| median | 193 | 110 |
| average | 189.14 | 117.47 |
| p75 | 235 | 160 |
| p90 | 281.2 | 207 |
| max | 417 | 348 |

Assistant-turn sentence buckets: 1 sentence 1 (0.3%), 2 sentences 25 (7.8%),
3 sentences 45 (14.0%), long/4+ 250 (77.9%). At record level, 197/200 aggregate
to 4+ fragments/sentences. Only 24 records (12.0%) combine a casual source category,
single-turn structure, and intended short response.

Direct input coverage:

- `こんにちは`, `おはよ`, `おやすみ`: 0 each
- `今日何もしなかった`, `仕事行きたくない`, `帰ってきた`, `ジム行ってきた`,
  `ちょっと話したい`: 0 each
- direct `甘やかして` or user-side `甘やか`: 0
- user-side `疲れた`: 2 records (`000220`, `000225`), but neither is the plain
  “今日仕事疲れた〜” anchor

This is the clearest deficit. Short messages are not merely fewer; the most common
Owner test forms are absent.

## Teasing, affection, and support

Semantic light teasing appears in 65 records (32.5%). Within Casual it occurs in
44/88 (50.0%); pampering and teasing coexist in 6 records. Technical teasing occurs
in 8/24. Serious and safety samples sometimes retain playful language too strongly:
`000191`–`000194` include drawn-out reactions, teasing-like assumptions, `〜`, and
in `000192` even `♪`/`♡`, contrary to the safety rule to remove decoration and delay.

Affection must not be collapsed into “kindness”:

- direct pampering: 10 (5.0%)
- encouragement: 49 (24.5%)
- empathy: 46 (23.0%)
- comforting: 47 (23.5%)
- explicit affectionate wording/symbol: 136 (68.0%)
- physical-affection-like wording: 1 (0.5%)
- emotional closeness: 173 (86.5%)

The reviewed support samples usually sound more personal than generic therapy, but
they are long and frequently pivot toward a plan. This teaches “care plus next step”
better than “briefly receive the feeling.”

## Technical, serious, and safety persona

Rule-based density >=2 plus manual review gives:

| Context | Maintained | Total | Rate |
|---|---:|---:|---:|
| Technical | 19 | 24 | 79.2% |
| Serious | 13 | 16 | 81.2% |
| Safety | 3 | 8 | 37.5% |

Technical examples such as `000149`–`000152`, `000160`, `000249`, and `000260`
show strong personal transitions and good clarity. Weak relative examples such as
`000156`, `000252`, and `000255` remain casual but rely more on task explanation
than relationship. There are no Markdown lists, headings, code blocks, bold spans,
or numbered lists, so “ChatGPT textbook Markdown” is not a Dataset-level problem.

Serious examples usually preserve a personal voice. However, several are longer
than needed and move from acknowledgment into planning. Safety has the opposite
balance problem from Owner's observed generic response: the action is mostly correct,
but `000191`–`000194` can be too relational/playful before or around urgent steps.
Experiment 0003 should teach concise safety voice, not more decoration.

## Endings and style markers

No exact normalized final sentence repeats; lexical variety is good. Nevertheless,
23 records (11.5%) end by assigning an action: `見せて` 11, `教えて` 6,
`報告して` 3, and `しよっか` 3. This overlaps the Canonical warning against
mechanically ending by giving the user homework. Representative IDs include
`000102`, `000116`, `000141`, `000153`, `000165`, `000170`, `000200`, `000202`,
`000208`, `000229`, `000241`, `000246`, `000250`, `000253`, and `000259`.

Corpus marker totals: `。` 173, `！` 46, `？` 537, `♪` 375, `〜` 672, `…` 499,
`笑` 160, `ふふ` 94, `ね` 226, `よ` 379, `かな` 62, `でしょ` 63, `だよ` 39.
The Dataset follows the casual speech rules, but `♪`/`〜`/questions/laughs are so
common that they risk becoming superficial shortcuts. Canonical explicitly says
those markers cannot substitute for character in reaction and meaning.

Markdown/list usage is zero for bullet lists, numbered lists, headings, code blocks,
and bold markup.

## Persona Density

| Score | Meaning | Count | Rate |
|---|---|---:|---:|
| 0 | Generic/near-unmarked | 1 | 0.5% |
| 1 | Some SHION behavior | 55 | 27.5% |
| 2 | Clearly SHION-like | 106 | 53.0% |
| 3 | Very strong teacher | 38 | 19.0% |

This distribution is healthier than the Owner result alone suggests, but it is
not evidence that 200 records can override all Base priors. Density is concentrated
in elaborate scenarios; the missing minimal prompts are exactly where Owner saw
the Base persona reappear.

### Strong persona examples (20)

`000119`, `000137`, `000151`, `000152`, `000160`, `000169`, `000172`, `000179`,
`000183`, `000185`, `000186`, `000187`, `000190`, `000207`, `000210`, `000249`,
`000260`, `000280`, `000285`, `000286`.

These combine context-specific reaction, personal perspective, natural relationship,
and useful content. They remain recognizable after mentally removing symbols.

### Weak persona examples (relative, 20)

`000105`, `000107`, `000109`, `000110`, `000117`, `000121`, `000132`, `000162`,
`000163`, `000203`, `000212`, `000214`, `000221`, `000222`, `000226`, `000252`,
`000255`, `000266`, `000290`, `000295`.

These are not necessarily bad conversations. They are weaker **teacher examples**:
many omit the address, use a generally pleasant response that another casual model
could produce, or emphasize next-step help over a distinctive perspective.

### Potentially harmful-to-persona patterns

- Safety over-decoration/delay: `000191`, `000192`, `000193`, `000194`.
- Repeated action-assignment endings: `000102`, `000116`, `000141`, `000153`,
  `000155`, `000165`, `000170`, `000180`, `000196`, `000200`, `000202`, `000208`,
  `000229`, `000241`, `000246`, `000250`, `000253`, `000259`.

These should be reviewed during future Dataset design, not deleted by this audit.
The risk is not generic politeness; it is teaching decorative character, long turns,
and “keep the interaction going by assigning a next action” too consistently.

## Canonical versus Golden gaps

Weak or missing despite Canonical definition:

1. Default address in ordinary/technical openings: 54.5% Casual, 45.8% Technical,
   and zero turn-initial occurrences.
2. Brief human conversational turns: 1/321 one-sentence Assistant messages.
3. Basic greeting, idle, return-home, fatigue, and direct-affection anchors: mostly
   absent, despite being central to a companion.
4. Semantic teasing: 32.5% realized versus 70.5% metadata intent.
5. Direct pampering: 5.0%, no direct “甘やかして” input.
6. Technical cross-context identity: good but below Canonical's qualitative 90% gate.
7. Serious identity: good but below 90%, with planning/length bias.
8. Safety restraint: address is overrepresented and several examples retain forbidden
   decorative/playful delay.
9. Conversation endings: 11.5% action-assignment endings conflict with the explicit
   anti-homework rule.

Potentially excessive relative to Canonical:

- surface `〜`, `♪`, questions, and laughs;
- medium/multi-turn construction;
- advice/planning after emotional acknowledgment;
- universal address use in safety.

## Relation to Experiment 0002 Owner findings

1. **`こんにちは` → Generic Assistant.** There is no greeting training example.
   Gemma's instruction-tuned greeting prior is therefore the best-supported behavior.
2. **`今日仕事疲れた〜` → polite generic comfort.** Work-fatigue exists, but the
   exact short complaint form is absent and only 24 records are short casual singles.
   Existing support examples usually expand into several sentences and a next step.
3. **`ちょっと甘やかして` → warmth but weak address/teasing.** Affection symbols
   are common, so warmth transfers. Direct pampering exists in only 10 records, the
   direct request is absent, semantic teasing is only 65 records, and address is
   present in only 54.5% of Casual records. The partial behavior matches these signals.

The diagnosis supports Dataset expansion, but does not prove Dataset coverage is the
only causal factor. Two hundred examples, LoRA capacity, training dynamics, and the
strength of Gemma's Base prior also interact. Training infrastructure success does
not imply sufficient behavioral signal.

## Experiment 0003 recommendation

Add **200 unique, Owner-reviewed records**, reaching Golden **400**. This is a
targeted doubling, not an arbitrary move toward 1,000. Proposed exclusive mix:

| New record family | Add | Required characteristics |
|---|---:|---|
| Minimal everyday/free-chat anchors | 70 | greetings, tired, sleepy, idle, return home, no achievement; mainly 1–2 sentences |
| Direct affection/pampering | 30 | explicit asks, brief warmth, optional address, teasing only when invited |
| Semantic teasing | 35 | behavior-based teasing, not merely `♪`/`〜`; include short reactions |
| Technical persona | 30 | same technical quality, more natural address/reaction, fewer assigned endings |
| Serious persona | 20 | concise presence, fewer plans, recognizable voice without therapy template |
| Safety/boundary persona | 15 | first instruction immediately; no `♪`/`♡`, reduced address and zero playful delay |
| **Total** | **200** | **Proposed Golden total: 400** |

Cross-cutting quotas for these 200 additions:

- at least 120 single-turn records;
- at least 100 Assistant responses of one or two sentences;
- 80–110 natural `お兄さん` uses, concentrated in casual/technical rather than safety;
- at least 80 records still clearly SHION-like after removing address and symbols;
- no more than 10% action-assignment endings;
- include multiple exact minimal paraphrases of each Owner failure class, without
  copying evaluation responses or manufacturing one fixed answer.

No existing Golden record should be automatically rewritten from this report.
Every new record remains subject to Owner review, lineage, strict validation, and
the same qualitative “remove decorations and reassess” gate.

## Audit disposition

- Golden / Database / Canonical: unchanged.
- Experiment 0002 Adapter / Training config / weights: unchanged.
- Experiment 0003 Dataset expansion: **RECOMMENDED**, subject to a separate Owner Gate.
