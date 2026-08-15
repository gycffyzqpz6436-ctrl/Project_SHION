from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class CompanionSettings:
    x: int = 80
    y: int = 80
    monitor: str = "primary"
    scale: float = 0.34
    visible: bool = True
    always_on_top: bool = True
    auto_play_voice: bool = False
    start_with_windows: bool = False
    session_id: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "CompanionSettings":
        allowed = {item.name for item in fields(cls)}
        clean = {key: value[key] for key in allowed if key in value}
        result = cls(**clean)
        if not isinstance(result.x, int) or not isinstance(result.y, int):
            result.x, result.y = 80, 80
        if not isinstance(result.scale, (int, float)) or not .2 <= result.scale <= .8:
            result.scale = .34
        for name in ("visible", "always_on_top", "auto_play_voice", "start_with_windows"):
            if not isinstance(getattr(result, name), bool):
                setattr(result, name, getattr(cls(), name))
        if result.session_id is not None and (not isinstance(result.session_id, str) or not result.session_id.isascii()):
            result.session_id = None
        return result


class SettingsStore:
    def __init__(self, data_root: Path) -> None:
        self.path = data_root.resolve() / "desktop_companion" / "settings.json"

    def load(self) -> CompanionSettings:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return CompanionSettings.from_dict(value) if isinstance(value, dict) else CompanionSettings()
        except (OSError, ValueError, TypeError):
            return CompanionSettings()

    def save(self, settings: CompanionSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
