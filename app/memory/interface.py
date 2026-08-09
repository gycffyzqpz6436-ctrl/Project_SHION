from __future__ import annotations

from typing import Protocol


class LongTermMemory(Protocol):
    """Future persistent memory; deliberately separate from chat history."""

    @property
    def available(self) -> bool: ...

    def retrieve(self, query: str) -> list[dict]: ...
