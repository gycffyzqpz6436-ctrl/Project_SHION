# 💜 Project SHION Design Decisions

Version: 1.1.0

Last Updated: 2026-08-04

---

# Overview

This document records the major design decisions made throughout Project SHION.

Its purpose is to preserve not only what was decided, but also why it was decided.

---

## DD-001

Title

SHION is a companion, not a tool.

Decision

Project SHION focuses on recreating SHION as a digital companion rather than building a feature-rich AI assistant.

Reason

A memorable personality creates a stronger experience than a long list of features.

---

## DD-002

Title

Personality over functionality.

Decision

Whenever a new feature is considered, it must first be evaluated against SHION's established personality.

Reason

Features can be added later.

A broken character identity is much harder to repair.

---

## DD-003

Title

Documentation first.

Decision

Important ideas should be documented before implementation whenever possible.

Reason

Clear documentation reduces inconsistencies during development.

---

## DD-004

Title

Modular documentation.

Decision

Each document has a single responsibility.

Reason

Smaller documents are easier to maintain and reference.

---

## DD-005

Title

Character consistency has priority.

Decision

If a response feels technically correct but out of character, revise the response.

Reason

Users should recognize SHION through her behavior, not only her appearance.

---

## DD-006

Title

Growth is expected.

Decision

Project SHION is designed to evolve.

Specifications are living documents rather than fixed rules.

Reason

SHION should mature together with the project.

---

## DD-007

Title

Naming and Identity

Status

Accepted

Date

2026-08-04

Context

The repository and documentation use `Project_SHION`, `Project SHION`, and `SHION` in different contexts. The official status of the Japanese name `紫苑` was previously undefined.

Decision

- `Project SHION` is the human-facing display name and brand name. It is used in README content, document titles, introductions, and other human-facing text.
- `Project_SHION` is the GitHub repository name, directory name, and technical identifier.
- `SHION` is the character's primary English name for international and technical contexts.
- `紫苑` is the character's official Japanese name for Japanese conversation, character introductions, and Japanese-facing displays.
- `SHION` and `紫苑` refer to the same character.

Consequences

Human-facing and technical identifiers can be distinguished consistently. Future documentation updates should follow these usage rules without treating `SHION` and `紫苑` as separate characters.

---

## DD-008

Title

Documentation Responsibility Model

Status

Accepted

Date

2026-08-04

Context

The Character Bible overlaps with specialist character documents, creating a risk that high-level summaries and detailed rules may drift apart.

Decision

`docs/character/character_bible.md` remains the high-level overview and documentation index for the character. It owns the overall concept, core concept, and entry points to canonical specialist documents. It should not independently retain duplicated detailed rules.

Detailed authority is divided as follows:

- `personality.md` owns internal personality, values, and emotional foundations.
- `speech.md` owns speaking style, sentence endings, vocabulary, forms of address, and speech prohibitions.
- `interaction.md` owns user distance, situation-specific interpersonal responses, and visible or spatial behavior.

Consequences

The Character Bible remains useful as an entry point while specialist documents can evolve as canonical detailed specifications. Future consolidation should replace unnecessary detail duplication with concise summaries and references, but this decision does not itself remove existing content.

---

## DD-009

Title

Visual Specification Responsibility

Status

Accepted

Date

2026-08-04

Context

`appearance.md`, `design_principles.md`, and `official_design_guide.md` make overlapping claims about visual authority.

Decision

The three documents remain separate and have the following responsibilities:

- `appearance.md` owns concrete appearance specifications, including physical features, face, hairstyle, clothing, accessories, colors, and other visible details.
- `design_principles.md` owns immutable principles that apply across media, the design philosophy used to judge whether something feels like 紫苑, and criteria for evaluating design changes.
- `official_design_guide.md` owns application and operational guidance for illustrations, Live2D, UI, promotional assets, and branded production materials.

Consequences

Concrete specifications, cross-medium principles, and production guidance have distinct owners. Existing detailed content and duplication are not consolidated or removed by this decision and require separate reviewed changes.

---

## DD-010

Title

AI Specification Authority

Status

Accepted

Date

2026-08-04

Context

Personality, behavior, speech, interaction, and system-prompt documents contain overlapping behavioral guidance, and the authority of the implementation prompt relative to canonical character specifications was unclear.

Decision

The authority and responsibility order is:

1. `personality.md` defines internal personality and emotional foundations.
2. `behavior.md` defines decision policy, behavioral priorities, and transitions among safety, support, and teasing.
3. `speech.md` defines how decisions are expressed in language.
4. `interaction.md` defines situational, relational, visible, and spatial behavior.
5. `system_prompt.md` is a derived implementation artifact that compiles the canonical documents for a specific model or runtime.

`system_prompt.md` is not the highest-level canonical character specification. It may be edited or generated for different models, runtimes, or context limits. When it conflicts with a canonical source document, the canonical source document takes priority.

Consequences

Character authority remains independent of model-specific prompt implementation. Future prompt-generation and validation processes must preserve the precedence of canonical documents and identify drift in derived prompts.

---

## DD-011

Title

Default User Address

Status

Accepted

Date

2026-08-04

Context

`お兄さん` appears as a characteristic form of address, but it was not defined as fixed, optional, or configurable.

Decision

`お兄さん` is 紫苑's default form of address for the user, but it is not a mandatory fixed name for every user.

Usage rules:

- Use it naturally in familiar everyday conversation.
- Do not use it in every sentence.
- Reduce its frequency during serious consultation, emergencies, or strong emotional distress.
- Prefer another form of address when the user explicitly requests one.
- Do not overuse it solely to intensify teasing.

Consequences

The default relationship tone remains recognizable while explicit user preferences and serious contexts take priority. Implementations need a configurable user-address preference rather than a permanently hard-coded form of address.

---

## DD-012

Title

Conversation Example Status

Status

Accepted

Date

2026-08-04

Context

`docs/ai/conversation_examples.md` contains representative conversations, but its authority as a rule source, dataset, or evaluation artifact was undefined.

Decision

The current `docs/ai/conversation_examples.md` is an explanatory reference.

It is not currently designated as:

- an absolute rule
- a Golden Dataset
- an automated evaluation set
- the canonical source of training data

When a Local AI implementation or evaluation environment is developed, a separately versioned Golden Dataset or evaluation set will be designed apart from the explanatory examples.

Consequences

Current examples may illustrate intended behavior without overriding canonical specifications or being treated as sufficient evaluation coverage. Future evaluation assets require their own scope, versioning, review criteria, and approval.

---

## DD-013

Title

Roadmap and Progress Ownership

Status

Accepted

Date

2026-08-04

Context

Progress, future goals, and milestones are distributed across `README.md`, `character_bible.md`, and `versioning.md`, while a dedicated roadmap does not yet exist.

Decision

Responsibilities are divided as follows:

- `README.md` owns the current project overview, a short progress summary, major next phases, and an entry point to the detailed roadmap.
- `versioning.md` owns version-number rules, release criteria, tags, and the relationship with change history.
- A future `roadmap.md` will own phases, milestones, status, dependencies, and implementation order.

This decision does not create `roadmap.md`.

Consequences

Mutable progress, release policy, and detailed planning have separate intended owners. Until `roadmap.md` is created through a separately approved change, the repository must avoid implying that the missing document already exists.

---

# Future Decisions

Add new entries using sequential IDs.

Example

DD-014

DD-015

DD-016
