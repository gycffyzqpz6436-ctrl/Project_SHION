"""Typed, persistence-neutral message contracts for SHION Chat vNext."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


PartType = Literal["text", "image", "audio", "attachment", "tool_result"]


@dataclass(frozen=True)
class MessagePart:
    type: PartType
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


@dataclass(frozen=True)
class ChatMessage:
    message_id: str
    session_id: str
    parent_id: str | None
    role: Literal["user", "assistant", "system", "tool"]
    created_at: str
    mode: str
    parts: tuple[MessagePart, ...]
    model: dict[str, Any] | None = None
    generation: dict[str, Any] | None = None
    feedback: Literal["good", "bad"] | None = None
    favorite: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parts"] = [part.to_dict() for part in self.parts]
        return payload
