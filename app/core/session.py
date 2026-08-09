from __future__ import annotations


class SessionStore:
    """In-memory short-term conversation context; never long-term memory."""

    def __init__(self) -> None:
        self.histories: dict[tuple[str, str], list[dict]] = {}

    def history(self, session_id: str, mode: str) -> list[dict]:
        return self.histories.setdefault((session_id, mode), [])

    def reset(self, session_id: str) -> None:
        for key in [key for key in self.histories if key[0] == session_id]:
            del self.histories[key]

    def clear(self) -> None:
        self.histories.clear()
