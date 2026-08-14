from __future__ import annotations

import time

from app.memory.long_term import DisabledLongTermMemory
from app.tools.registry import ToolRegistry, default_tool_registry


class ShionOrchestrator:
    """Coordinates SHION components without granting the model direct capabilities."""

    def __init__(self, tools: ToolRegistry | None = None, long_term_memory=None) -> None:
        self.tools = tools or default_tool_registry()
        self.long_term_memory = long_term_memory or DisabledLongTermMemory()

    def respond(self, model, session_id: str, mode: str, history: list[dict], message: str,
                character_id: str = "shion") -> tuple[str, int | dict]:
        memory_context = ""
        memory_items = []
        memory_started = time.perf_counter()
        if self.long_term_memory.available:
            try:
                memory_context, memory_items = self.long_term_memory.relevant_context(
                    message, character_id=character_id, conversation_id=session_id
                )
                self.long_term_memory.last_error = None
            except Exception as error:
                # Memory enhances Chat but never controls Chat availability.
                self.long_term_memory.last_error = f"Memory retrieval unavailable: {type(error).__name__}"
        memory_retrieval_ms = round((time.perf_counter() - memory_started) * 1000, 3)
        result = (model.generate(session_id, mode, history, message, memory_context=memory_context)
                  if memory_context else model.generate(session_id, mode, history, message))
        if isinstance(result[1], dict):
            result[1]["memory_retrieval_ms"] = memory_retrieval_ms
            result[1]["memory_items"] = len(memory_items)
        return result

    def capability_status(self) -> dict:
        return {"long_term_memory": self.long_term_memory.available, "tools": self.tools.status()}
