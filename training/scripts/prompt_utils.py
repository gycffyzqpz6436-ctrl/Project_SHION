"""Canonical prompt extraction shared by local evaluation scripts."""

from pathlib import Path


def canonical_system_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index("# Identity\n") + len("# Identity\n")
    end = text.index("# Synchronization Workflow\n")
    return text[start:end].strip()


def system_prompt_for_mode(mode: str, path: Path) -> str | None:
    if mode == "canonical":
        return canonical_system_prompt(path)
    if mode == "minimal":
        return None
    raise ValueError(f"unknown evaluation mode: {mode}")

