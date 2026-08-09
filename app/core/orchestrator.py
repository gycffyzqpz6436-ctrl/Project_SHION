from __future__ import annotations

from app.memory.long_term import DisabledLongTermMemory
from app.tools.registry import ToolRegistry, default_tool_registry


class ShionOrchestrator:
    """Coordinates SHION components without granting the model direct capabilities."""

    def __init__(self, tools: ToolRegistry | None = None, long_term_memory=None) -> None:
        self.tools = tools or default_tool_registry()
        self.long_term_memory = long_term_memory or DisabledLongTermMemory()

    def respond(self, model, session_id: str, mode: str, history: list[dict], message: str) -> tuple[str, int]:
        # Phase 1 is conversation-only. Tool and memory routing remain default-disabled.
        return model.generate(session_id, mode, history, message)

    def capability_status(self) -> dict:
        return {"long_term_memory": self.long_term_memory.available, "tools": self.tools.status()}
