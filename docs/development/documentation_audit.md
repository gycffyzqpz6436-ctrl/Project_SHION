# Project SHION Documentation Audit

Version: 2.0.0

Last Updated: 2026-08-04

---

## 1. Audit Scope

### Purpose

This audit records the current documentation structure of Project SHION and identifies:

- broken or ambiguous references
- competing source-of-truth claims
- content inconsistencies
- naming and terminology issues
- intentional or acceptable duplication
- design decisions that remain open before implementation

This audit does not resolve character, visual, speech, relationship, implementation, or branding decisions. It records confirmed facts separately from inferred responsibilities and recommendations.

### Confirmed Facts

The repository currently contains 27 Markdown documents, not 26:

- 1 root document
- 6 documents in `docs/ai/`
- 11 documents in `docs/character/`
- 6 documents in `docs/development/`
- 3 documents in `docs/live2d/`

All 27 Markdown documents were reviewed:

#### Root

- `README.md`

#### AI

- `docs/ai/behavior.md`
- `docs/ai/conversation_examples.md`
- `docs/ai/memory.md`
- `docs/ai/prompt_design.md`
- `docs/ai/system_flow.md`
- `docs/ai/system_prompt.md`

#### Character

- `docs/character/appearance.md`
- `docs/character/brand_assets.md`
- `docs/character/brand_philosophy.md`
- `docs/character/character_bible.md`
- `docs/character/design_principles.md`
- `docs/character/expressions.md`
- `docs/character/interaction.md`
- `docs/character/official_design_guide.md`
- `docs/character/personality.md`
- `docs/character/room.md`
- `docs/character/speech.md`

#### Development

- `docs/development/architecture.md`
- `docs/development/coding_standards.md`
- `docs/development/contribution_guide.md`
- `docs/development/design_decisions.md`
- `docs/development/documentation_audit.md`
- `docs/development/versioning.md`

#### Live2D

- `docs/live2d/expression_mapping.md`
- `docs/live2d/model_specification.md`
- `docs/live2d/motion_specification.md`

### Audit Boundaries

Only documentation was audited. The repository currently contains no implementation source code, tests, image assets, audio assets, Live2D model files, or concrete brand asset files to compare with the written specifications.

No Project_NONO material was used in this audit.

---

## 2. Repository Documentation Overview

### Confirmed Documentation Structure

| Area | Documents | Confirmed role |
|---|---:|---|
| Root | 1 | Project introduction and high-level progress summary |
| AI | 6 | Behavior, examples, memory, prompt composition, processing flow, and a proposed system prompt |
| Character | 11 | Character identity, personality, speech, interaction, appearance, environment, expressions, and brand direction |
| Development | 6 | Architecture, engineering policies, contribution rules, decision history, audit, and version strategy |
| Live2D | 3 | Model preparation, motion behavior, and expression implementation guidance |

### Confirmed Repository State

- `README.md` marks the Character Bible, Character Design, Expressions, Pose References, and Personality Design as complete.
- `README.md` marks Live2D, Local AI, Voice, and Desktop Assistant as pending.
- `character_bible.md` contains a separate Future Goals checklist.
- `versioning.md` contains a separate milestone sequence from `v0.1.0` through `v1.0.0`.
- The repository has documentation for Live2D and Local AI concepts, but it has no corresponding implementation or asset files.
- There is no dedicated voice specification.
- Desktop-assistant responsibilities appear in `architecture.md` and `interaction.md`, but there is no dedicated desktop implementation specification.
- There is no `roadmap.md`.
- There is no `CHANGELOG.md`.

### Inferred Repository Stage

The following is an inference, not a declared project status:

> Project SHION appears to be in a documentation-foundation and pre-implementation design stage.

This inference is based on the presence of broad specification documents and the absence of implementation code and production assets. It should not be treated as an official release designation until the project owner confirms it.

---

## 3. Canonical Source Map

The table below separates confirmed declarations from inferred responsibilities. An inferred responsibility is not a final source-of-truth decision.

| Document | Responsibility | Status |
|---|---|---|
| `README.md` | Repository entry point, vision, and high-level status | Confirmed by content |
| `docs/character/character_bible.md` | High-level character overview and navigation entry point | Inferred; the previous audit also recommended this role |
| `docs/character/personality.md` | Internal personality, emotional baseline, values, likes, dislikes, and serious-situation baseline | Confirmed by document purpose |
| `docs/character/speech.md` | Language, tone, signature expressions, sentence endings, teasing boundaries, and verbal expression | Confirmed by document purpose |
| `docs/character/interaction.md` | Visible interaction patterns, presence, activity-specific behavior, and spatial behavior | Confirmed by document purpose |
| `docs/character/appearance.md` | Detailed physical appearance, clothing, accessories, palette, and silhouette | Confirmed by document purpose |
| `docs/character/design_principles.md` | Cross-medium identity and design principles | Confirmed by document purpose; authority level is disputed |
| `docs/character/official_design_guide.md` | Official visual identity and immutable visual elements | Confirmed by document purpose; authority level is disputed |
| `docs/character/expressions.md` | Character-facing facial-expression definitions and usage | Confirmed by document purpose |
| `docs/character/room.md` | SHION's virtual room and environmental design | Confirmed by document purpose |
| `docs/character/brand_philosophy.md` | Project vision, brand values, and long-term creative direction | Confirmed by document purpose |
| `docs/character/brand_assets.md` | Requirements and usage guidance for future branding assets | Confirmed by document purpose; it does not contain the assets themselves |
| `docs/ai/behavior.md` | Behavioral priorities, initiative, feedback handling, mistakes, and decision checks | Confirmed by document purpose; authority relative to `system_prompt.md` is disputed |
| `docs/ai/conversation_examples.md` | Representative conversation examples | Confirmed by document purpose; Golden Example status is not established |
| `docs/ai/memory.md` | Memory philosophy, categories, retention, and forgetting | Confirmed by document purpose |
| `docs/ai/prompt_design.md` | Modular prompt-layer design and composition | Confirmed by document purpose |
| `docs/ai/system_flow.md` | Conceptual interaction-processing pipeline | Confirmed by document purpose |
| `docs/ai/system_prompt.md` | Proposed core system prompt for Local AI implementations | Confirmed by document purpose; final runtime authority is not established |
| `docs/live2d/model_specification.md` | Live2D source-art and model preparation guidance | Confirmed by document purpose |
| `docs/live2d/motion_specification.md` | Live2D motion set and transition behavior | Confirmed by document purpose |
| `docs/live2d/expression_mapping.md` | Intended bridge from character expressions to Live2D expression behavior | Confirmed by purpose; concrete parameter mapping is incomplete |
| `docs/development/architecture.md` | Conceptual system architecture and module responsibilities | Confirmed by document purpose |
| `docs/development/coding_standards.md` | General code style and naming guidance | Confirmed by document purpose |
| `docs/development/contribution_guide.md` | Contribution, commit, documentation, and review expectations | Confirmed by document purpose |
| `docs/development/design_decisions.md` | Record of major project decisions and their rationale | Confirmed by document purpose |
| `docs/development/documentation_audit.md` | Documentation inventory, conflicts, open decisions, and recommended resolution order | Confirmed by document purpose |
| `docs/development/versioning.md` | Proposed versioning policy and milestone sequence | Confirmed by document purpose |

### Canonical Status That Is Not Yet Decided

The audit does not select a final canonical source for:

- immutable visual specifications
- AI behavior and runtime instruction precedence
- project progress and roadmap status
- the normative status of conversation examples

These conflicts are described below.

---

## 4. Broken or Ambiguous References

### BR-001 — Missing `live2d.md`

**Confirmed fact**

`docs/character/character_bible.md` refers to `live2d.md`, but no file with that name exists.

**Impact**

Readers cannot reach the intended Live2D source. It is unclear whether the intended target is the whole `docs/live2d/` directory or one of its three specifications.

**Recommended direction**

After confirming the intended target, replace the reference with explicit links to the relevant existing Live2D documents. Do not create `live2d.md` solely to satisfy this reference without first deciding its responsibility.

### BR-002 — Missing `roadmap.md`

**Confirmed fact**

The previous version of this audit listed `roadmap.md` as a future audit target, but no `roadmap.md` exists.

**Impact**

The reference implies that a dedicated roadmap is already part of the documentation set. Progress information remains distributed across other documents.

**Recommended direction**

Decide whether roadmap authority should remain in an existing document or move to a future dedicated document. Do not create the file as part of this audit.

### BR-003 — Missing `CHANGELOG.md`

**Confirmed fact**

`docs/development/versioning.md` states that every version should include an update to `CHANGELOG.md`, but no `CHANGELOG.md` exists.

**Impact**

The documented release process cannot currently be followed as written.

**Recommended direction**

Before the first formal release, either add a changelog in a separately approved change or revise the versioning policy. Do not create it as part of this audit.

### BR-004 — Ambiguous `expressions.md` reference in Live2D specification

**Confirmed fact**

`docs/live2d/model_specification.md` says that expressions should follow `expressions.md`. There is no `expressions.md` in `docs/live2d/`; the existing file is `docs/character/expressions.md`.

**Impact**

The intended canonical expression definition is likely but not explicit, and a relative link created from the current text would point to a missing file.

**Recommended direction**

If the character expression document is confirmed as the intended source, use an explicit relative path to `../character/expressions.md`.

### BR-005 — Bare filename references across directories

**Confirmed fact**

`prompt_design.md`, `system_flow.md`, and other documents refer to files such as `personality.md`, `interaction.md`, `speech.md`, and `behavior.md` without paths or Markdown links.

**Impact**

Several references appear to point to the current directory even though the target files are in another directory. Navigation and automated link checking are unreliable.

**Recommended direction**

Convert references to explicit relative Markdown links after canonical responsibilities are confirmed.

### BR-006 — Official assets are referenced but not present

**Confirmed fact**

`brand_assets.md` and `official_design_guide.md` refer to an official signature, logo, and icon. No corresponding asset files are present in the repository.

**Impact**

The documents can currently define requirements only; they cannot identify concrete approved assets.

**Recommended direction**

Treat these elements as planned assets until approved files and usage metadata exist. Do not infer that a described motif is an approved final asset.

---

## 5. Source-of-Truth Conflicts

### ST-001 — Visual specification authority

**Documents**

- `docs/character/appearance.md`
- `docs/character/design_principles.md`
- `docs/character/official_design_guide.md`

**Confirmed facts**

- `appearance.md` states that every visual representation should follow it.
- `design_principles.md` defines core principles intended to remain consistent across media.
- `official_design_guide.md` states that it defines the official visual identity and that every visual implementation should follow it.
- The previous audit recommended `design_principles.md` as the authoritative source for immutable visual specifications.
- `official_design_guide.md` was added after the original audit scope was established.

**Conflict**

Three documents claim overlapping authority over immutable or universal visual identity. The previous audit's conclusion is no longer sufficient because it did not evaluate the later official design guide.

**Impact**

Illustration, Live2D, 3D, image-generation, and branding work may select different sources when details diverge.

**Recommended direction**

The project owner should assign non-overlapping authority, for example:

- physical detail and wardrobe specification
- immutable cross-medium identity
- official usage and brand presentation

This example is a proposed responsibility split, not a decision. No one document is selected by this audit.

### ST-002 — Personality, behavior, interaction, and runtime instruction authority

**Documents**

- `docs/character/personality.md`
- `docs/character/speech.md`
- `docs/character/interaction.md`
- `docs/ai/behavior.md`
- `docs/ai/system_prompt.md`

**Confirmed facts**

- `personality.md` defines internal traits and emotional stability.
- `speech.md` defines verbal expression and conversation rules.
- `interaction.md` defines visible and situational interaction behavior.
- `behavior.md` defines behavioral priorities, initiative, feedback, and decision checks.
- `system_prompt.md` calls itself the primary behavioral specification for Local AI implementations.

**Conflict**

The documents are mostly directionally consistent, but the boundary between character truth, behavioral policy, and executable runtime instruction is not explicit. `behavior.md` and `system_prompt.md` both make broad behavioral claims.

**Impact**

Future prompt assembly may duplicate rules, produce unclear precedence, or allow runtime instructions to drift from the character specifications.

**Recommended direction**

Define a precedence model before Local AI implementation. A possible model would distinguish:

- character facts
- behavioral policy
- language realization
- interaction presentation
- compiled runtime prompt

This model is a proposal only. The audit does not choose the final AI behavior authority.

### ST-003 — Progress, future goals, and milestone authority

**Documents**

- `README.md`
- `docs/character/character_bible.md`
- `docs/development/versioning.md`

**Confirmed facts**

- `README.md` contains a completion checklist.
- `character_bible.md` contains a separate Future Goals checklist.
- `versioning.md` defines planned milestones.
- The checklists and milestones use different levels of detail.

**Conflict**

No document is declared as the authoritative current project status. Static character documentation contains mutable project-progress information.

**Impact**

Progress can become stale or contradictory when only one checklist is updated.

**Recommended direction**

Choose one status authority and make the other documents link to it or provide explicitly non-authoritative summaries. The audit does not decide whether that authority should be the README, a future roadmap, or another project-management source.

### ST-004 — Status of conversation examples

**Documents**

- `docs/ai/conversation_examples.md`
- `docs/character/speech.md`
- `docs/character/personality.md`
- `docs/ai/system_prompt.md`

**Confirmed fact**

`conversation_examples.md` describes its examples as representative references and says that examples are especially important. It does not declare them to be Golden Examples, tests, or higher-priority rules.

**Conflict**

The normative weight of examples relative to written rules is not defined.

**Impact**

Model evaluation and prompt design cannot consistently determine whether an example should override, illustrate, or be revised to match a rule.

**Recommended direction**

Define whether examples are illustrative, normative, evaluative, or versioned test fixtures. Do not assign Golden Example status without an explicit project decision.

---

## 6. Content Inconsistencies

### CI-001 — Live2D clothing layers do not match the appearance specification

**Documents**

- `docs/character/appearance.md`
- `docs/live2d/model_specification.md`

**Confirmed facts**

- `appearance.md` defines the main outer garment as an oversized black hoodie.
- `model_specification.md` lists `Jacket` and `Belt` as required clothing layer groups.
- `appearance.md` does not define a belt as part of the main or casual outfit.

**Inconsistency**

It is unclear whether `Jacket` is a generic technical label for the hoodie, whether it represents another outfit, and whether the belt is an approved element or a leftover assumption.

**Impact**

Source-art preparation may add, omit, or incorrectly name visible clothing elements.

**Recommended direction**

Confirm the intended outfit and then align technical layer names with the approved visual specification. Do not add or remove clothing elements based on this audit alone.

### CI-002 — Expression inventories do not match

**Documents**

- `docs/character/expressions.md`
- `docs/live2d/expression_mapping.md`

**Confirmed facts**

- `expressions.md` defines Default, Playful, Serious, Thinking, Embarrassed, Happy, Amused, and Disappointed.
- `expression_mapping.md` defines Default, Playful, Happy, Thinking, Serious, and Embarrassed.
- Amused and Disappointed have no Live2D mapping.
- The expression priority list omits Embarrassed.
- `expression_mapping.md` describes visual states but does not specify concrete Live2D parameter IDs, ranges, or values.

**Inconsistency**

The character-level inventory and implementation-level inventory are not aligned, and the claimed mapping is not yet implementation-ready.

**Impact**

Expression selection, priority handling, rigging, and automated emotion-to-expression control remain underspecified.

**Recommended direction**

First confirm the supported initial expression set. Then define explicit mapping status for every character expression and add concrete parameter information during Live2D implementation planning.

### CI-003 — Virtual room and physical-presence language remain ambiguous

**Documents**

- `docs/character/character_bible.md`
- `docs/character/room.md`
- `docs/character/interaction.md`
- `docs/live2d/motion_specification.md`

**Confirmed facts**

- `character_bible.md` says SHION lives inside the user's computer.
- `room.md` defines a digital personal room.
- `interaction.md` says SHION shares the user's workspace and may touch the monitor frame or look over the user's shoulder.
- Live2D future motions include actions in the room, such as sitting on the bed and looking out the window.

**Inconsistency**

The documents do not consistently distinguish:

- SHION's virtual room
- the user's physical room
- a desktop overlay or composited presentation
- metaphorical spatial language

**Impact**

Background art, Live2D staging, desktop UI, spatial interaction, and future vision features may implement incompatible interpretations.

**Recommended direction**

Define the presentation model before desktop or Live2D scene implementation. Do not remove existing interaction ideas until their intended context is confirmed.

### CI-004 — README completion claims exceed available repository artifacts

**Confirmed facts**

- `README.md` marks Pose References as complete.
- The repository contains no dedicated pose-reference document or image assets.
- `README.md` says the repository contains visual references, but no image assets are present.

**Inconsistency**

The meaning of "complete" and "visual references" is not supported by identifiable repository artifacts.

**Impact**

New contributors may assume that required design inputs already exist.

**Recommended direction**

Confirm whether these artifacts exist outside the repository, are represented indirectly by text specifications, or should remain pending.

### CI-005 — Document versions and project versions can be confused

**Confirmed facts**

- Most specification documents declare `Version: 1.0.0`.
- `versioning.md` defines project milestones beginning with `v0.1.0` and ending with the first stable public release at `v1.0.0`.
- No document explicitly defines whether its header version is independent from the project release version.

**Inconsistency**

The same version format is used for document revisions and proposed project releases without a stated relationship.

**Impact**

Readers may interpret version 1.0.0 documents as evidence that the project has reached stable release status.

**Recommended direction**

Define separate document-version and project-release semantics before formal release management begins.

### CI-006 — Architecture is more concrete than the selected implementation stack

**Confirmed facts**

- `architecture.md` defines Desktop Application, Live2D, AI Engine, Memory System, and Tool Calling modules.
- `coding_standards.md` uses Python examples.
- No language, framework, operating-system target, model runtime, storage format, or desktop technology is selected.

**Inconsistency**

The architecture communicates module boundaries, but some readers may interpret examples or diagrams as implementation commitments that have not actually been recorded.

**Impact**

Implementation could begin with unstated assumptions.

**Recommended direction**

Record stack decisions separately when they are made. Until then, label the architecture as conceptual and code snippets as illustrative.

---

## 7. Naming and Terminology Issues

### NT-001 — `Project SHION` and `Project_SHION`

**Confirmed facts**

- The repository name is `Project_SHION`.
- Documentation primarily uses `Project SHION`.
- Both forms appear meaningful in different contexts, but no usage rule is documented.

**Open decision**

Decide whether `Project SHION` is the display or brand name and `Project_SHION` is only a repository or technical identifier. This audit does not establish that rule.

### NT-002 — `SHION` and `紫苑`

**Confirmed fact**

The audited documentation uses `SHION` as the character name. It does not define `紫苑` as an official Japanese name, display name, alias, or localization.

**Open decision**

Decide whether `紫苑` is an official Japanese form and, if so, where each form should be used.

### NT-003 — User relationship and the term `お兄さん`

**Confirmed facts**

- `personality.md` and `system_prompt.md` describe the user as a development partner or long-term partner.
- `speech.md` lists `お兄さんさぁ〜♪` as a signature expression.
- `conversation_examples.md` repeatedly addresses the user as `お兄さん`.
- No document states whether `お兄さん` is fixed, user-specific, optional, configurable, or context-dependent.

**Open decision**

Define the status and boundaries of `お兄さん` without changing the relationship or speech style during this audit.

### NT-004 — Live2D clothing terminology

**Confirmed fact**

`appearance.md` uses `hoodie`, while `model_specification.md` uses `Jacket`.

**Open decision**

Confirm whether these terms refer to the same garment or different approved outfits.

### NT-005 — Asset status terminology

**Confirmed fact**

The documents use `official logo`, `official signature`, `official icon`, and `recommended elements`, but do not distinguish consistently between approved assets, requirements, concepts, and future proposals.

**Recommended direction**

Introduce explicit status labels such as proposed, required, approved, and implemented when asset work begins.

---

## 8. Intentional or Acceptable Duplication

The following repetition is currently consistent and can be useful for local readability. It should not be removed automatically.

### Character identity summary

`README.md`, `character_bible.md`, `brand_philosophy.md`, and `design_principles.md` repeat the goals of originality, consistency, longevity, intelligence, calmness, and playfulness.

This is acceptable when:

- the README remains a short project introduction
- the Character Bible remains a high-level character entry point
- brand philosophy explains project values
- design principles explain cross-medium constraints

### Serious-situation behavior

`personality.md`, `speech.md`, `interaction.md`, `behavior.md`, `system_prompt.md`, and `conversation_examples.md` consistently describe reducing teasing, remaining calm, and providing genuine support.

This is acceptable when each document limits itself to its own layer:

- internal emotional baseline
- verbal expression
- visible interaction
- behavioral decision policy
- runtime prompt representation
- illustrative example

The responsibility split is inferred and still requires confirmation.

### Subtle emotional expression

`expressions.md`, `expression_mapping.md`, `model_specification.md`, and `motion_specification.md` consistently reject exaggerated reactions and favor subtle movement.

This is acceptable because the documents address different implementation layers. Shared principles should eventually link back to an agreed canonical source rather than independently redefining thresholds.

### Long-term companion philosophy

`README.md`, `character_bible.md`, `personality.md`, `system_prompt.md`, `memory.md`, `architecture.md`, `brand_philosophy.md`, and `design_decisions.md` repeat that SHION is a long-term companion rather than a generic chatbot or tool.

This repetition is consistent. A short canonical project statement would reduce future drift while allowing concise summaries elsewhere.

### Visual identity summary

Hair color, purple gradient, purple eyes, two-side-up hairstyle, calm expression, and slim silhouette appear in several character and Live2D documents.

This is necessary for implementation context, but detailed values should ultimately be owned by a confirmed visual source and referenced from implementation documents.

---

## 9. Open Design Decisions

The following items are unresolved. This audit intentionally does not decide them.

| ID | Open decision | Affected documents |
|---|---|---|
| OD-001 | Which document is authoritative for immutable visual specifications? | `appearance.md`, `design_principles.md`, `official_design_guide.md` |
| OD-002 | How should physical detail, cross-medium principles, and official brand presentation be divided? | Same as OD-001, plus `brand_assets.md` |
| OD-003 | Which source defines AI behavioral truth, and how is runtime precedence compiled? | `personality.md`, `speech.md`, `interaction.md`, `behavior.md`, `system_prompt.md`, `prompt_design.md` |
| OD-004 | Are conversation examples illustrative, normative, evaluative, or Golden Examples? | `conversation_examples.md` and all conversation specifications |
| OD-005 | Which source is authoritative for current progress and future milestones? | `README.md`, `character_bible.md`, `versioning.md` |
| OD-006 | Should a dedicated roadmap exist, or should an existing document own roadmap status? | `README.md`, `versioning.md`, missing `roadmap.md` |
| OD-007 | Should a changelog be created before the first formal release, or should the policy change? | `versioning.md`, missing `CHANGELOG.md` |
| OD-008 | Is `Project SHION` the display name and `Project_SHION` only a technical identifier? | Repository-wide |
| OD-009 | Is `紫苑` an official Japanese name, alias, or localization? | Repository-wide |
| OD-010 | Is `お兄さん` fixed, configurable, user-specific, optional, or context-dependent? | `speech.md`, `conversation_examples.md`, relationship specifications |
| OD-011 | Does `Jacket` mean the approved hoodie, and is `Belt` part of an approved outfit? | `appearance.md`, `model_specification.md` |
| OD-012 | Which expressions are required for the first Live2D implementation? | `expressions.md`, `expression_mapping.md`, `model_specification.md` |
| OD-013 | How is SHION's virtual room presented relative to the user's physical workspace? | `character_bible.md`, `room.md`, `interaction.md`, Live2D documents |
| OD-014 | Are official logo, signature, and icon concepts, requirements, or approved assets? | `brand_assets.md`, `official_design_guide.md` |
| OD-015 | How are document versions separated from project release versions? | All versioned documents, `versioning.md` |
| OD-016 | What evidence or artifact supports completed Pose References and visual references? | `README.md`, character and Live2D documentation |
| OD-017 | Which implementation stack and platform constraints are approved? | `architecture.md`, `coding_standards.md` |
| OD-018 | What are the voice identity and synthesis requirements? | README roadmap; no dedicated voice document |
| OD-019 | What are the desktop assistant's UI, permissions, privacy, and safety boundaries? | `architecture.md`, `interaction.md` |

---

## 10. Recommended Resolution Order

These are recommendations, not project decisions.

### 1. Confirm documentation authority and terminology

Resolve:

- visual source-of-truth responsibilities
- AI behavior and prompt precedence
- progress and roadmap authority
- `Project SHION` / `Project_SHION`
- `SHION` / `紫苑`
- the status of `お兄さん`

Reason:

These decisions affect many later edits and reduce the risk of fixing links toward the wrong canonical source.

### 2. Repair confirmed references without changing specifications

After authority is confirmed:

- replace the missing `live2d.md` reference
- make the Live2D `expressions.md` target explicit
- convert bare filenames into explicit relative Markdown links
- resolve how documentation should refer to the absent roadmap and changelog

Reason:

This is small, verifiable maintenance work once target ownership is known.

### 3. Reconcile implementation-facing inventories

Resolve:

- hoodie, `Jacket`, and `Belt`
- the initial Live2D expression set
- expression priorities and parameter mappings
- the virtual-room presentation model

Reason:

These items directly affect source-art preparation, rigging, animation, desktop UI, and AI-to-Live2D control.

### 4. Separate project status from stable character specifications

Choose one progress authority and remove or clearly label duplicate mutable checklists.

Reason:

Character identity documents should not silently become stale when implementation progress changes.

### 5. Record implementation decisions before coding

Before implementation, document approved decisions for:

- platform and technology stack
- model runtime
- memory storage and privacy
- tool permissions and safety boundaries
- voice requirements
- asset approval status

Reason:

The current architecture is conceptual and should not be mistaken for a selected implementation.

---

## 11. Audit Conclusion

### Confirmed Facts

- Project SHION has 27 Markdown documents in the audited scope.
- The documentation provides a broad and mostly consistent character and system direction.
- Several references are missing or ambiguous.
- Visual authority, AI behavioral authority, and progress authority are distributed across competing documents.
- Live2D expression and clothing specifications are not fully aligned with character specifications.
- Several planned assets and process documents are referenced but do not exist.
- The repository contains documentation but no implementation or production asset files.

### Inferred Responsibilities

Most documents have a recognizable intended responsibility, but several authority boundaries remain inferred rather than explicitly approved.

### Conflicts

The highest-impact conflicts are:

1. competing visual source-of-truth claims
2. unclear precedence among personality, behavior, speech, interaction, and system prompt documents
3. distributed progress and milestone tracking
4. mismatched expression inventories
5. unresolved Live2D clothing terminology

### Open Decisions

Open decisions are recorded in Section 9. None are resolved by this audit.

### Recommended Next Actions

1. Approve a canonical responsibility map without changing character content.
2. Repair confirmed references in a separate, narrowly scoped documentation change.
3. Reconcile Live2D expression and clothing inventories before asset production or rigging.

This audit should be repeated after authority decisions are recorded and before the first implementation milestone or minor release.
