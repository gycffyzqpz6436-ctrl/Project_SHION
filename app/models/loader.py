from __future__ import annotations

from pathlib import Path

from app.runtime.model_runtime import LocalModelRuntime


def load_conversation_model(common: Path, alias: str, spec: dict, adapter: Path | None = None):
    """Create an allowlisted offline conversation-model adapter."""
    return LocalModelRuntime(common, alias, spec, adapter)
