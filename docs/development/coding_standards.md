# 💜 Project SHION Coding Standards

Version: 1.0.0

Last Updated: 2026-07-20

---

# Purpose

This document defines the coding standards for Project SHION.

The goal is to maintain a clean, readable, and scalable codebase.

---

# General Principles

- Write code for humans first.
- Prefer clarity over cleverness.
- Keep functions small and focused.
- Avoid unnecessary complexity.

---

# Naming Conventions

## Variables

Use descriptive names.

Good

```python
current_expression
memory_manager
conversation_history
```

Bad

```python
tmp
x
data1
```

---

## Functions

Use verbs.

Examples

```python
load_memory()
save_memory()
generate_reply()
update_expression()
```

---

## Classes

Use PascalCase.

Examples

```python
MemoryManager
ConversationEngine
ExpressionController
```

---

## Constants

Use UPPER_SNAKE_CASE.

Examples

```python
MAX_MEMORY_SIZE
DEFAULT_MODEL
CONFIG_PATH
```

---

# Project Structure

Each module should have a single responsibility.

Example

- Memory
- Conversation
- Live2D
- Audio
- UI
- Tool Calling

Avoid mixing unrelated logic.

---

# Documentation

Every public class and function should include documentation.

Complex logic should explain why it exists.

Avoid comments that simply repeat the code.

---

# Error Handling

Errors should provide meaningful messages.

Never hide exceptions without logging.

Fail safely whenever possible.

---

# Formatting

Follow the formatter and linter adopted by the project.

Keep formatting consistent across all files.

---

# Philosophy

Readable code is part of SHION's personality.

Calm, organized, and thoughtful.
