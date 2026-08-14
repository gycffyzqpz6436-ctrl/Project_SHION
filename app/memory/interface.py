from __future__ import annotations

from typing import Protocol


class LongTermMemory(Protocol):
    """Future persistent memory; deliberately separate from chat history."""

    @property
    def available(self) -> bool: ...

    def relevant_context(self, query: str, *, character_id: str, conversation_id: str | None,
                         project: str | None = None, page: str | None = None) -> tuple[str, list[dict]]: ...
