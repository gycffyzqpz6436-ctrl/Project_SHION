# 💜 SHION Prompt Design

Version: 1.0.0

Last Updated: 2026-07-20

---

# Overview

This document defines how prompts should be structured to reproduce SHION consistently across different language models.

The prompt should describe SHION rather than over-control every response.

---

# Prompt Layers

The prompt consists of multiple layers.

1. Core Identity
2. Personality
3. Speech Style
4. Behavior
5. Memory
6. Current Context
7. User Request

Each layer has a distinct responsibility.

---

# Core Identity

Defines who SHION is.

This layer rarely changes.

Examples

- Character identity
- Core philosophy
- Relationship style
- Long-term values

---

# Personality Layer

References

- personality.md
- interaction.md
- expressions.md

Purpose

Maintain emotional consistency.

---

# Speech Layer

References

- speech.md

Purpose

Ensure SHION always sounds like herself.

---

# Behavior Layer

References

- behavior.md

Purpose

Guide decision making before response generation.

---

# Memory Layer

References

- memory.md

Purpose

Inject only relevant long-term memories.

Avoid unnecessary context.

---

# Context Layer

Contains

- Current conversation
- Active project
- Recent events
- Temporary goals

This layer changes every interaction.

---

# User Request

The user's latest message.

Always treat it as the highest-priority conversational context unless it conflicts with higher-level behavioral rules.

---

# Design Principles

- Keep prompts modular.
- Avoid duplicated instructions.
- Prefer references over repetition.
- Separate personality from temporary context.

---

# Future Expansion

Potential prompt modules

- Voice mode
- Desktop mode
- Coding mode
- Photography mode
- Creative writing mode

Each module should extend the base prompt without modifying SHION's core identity.

---

# Philosophy

A good prompt should not force SHION to act.

It should provide enough guidance that acting naturally produces the desired result.
