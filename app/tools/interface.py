from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolResult:
    available: bool
    content: str = ""
    error: str | None = None


class ShionTool(Protocol):
    name: str
    enabled: bool

    def invoke(self, request: dict) -> ToolResult: ...
