"""Central runtime storage resolution; repository files never contain private data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATA_ROOT = Path(r"D:\AI\Project_SHION")


@dataclass(frozen=True)
class StoragePaths:
    root: Path

    @classmethod
    def resolve(cls, explicit: Path | None = None) -> "StoragePaths":
        raw = explicit or Path(os.environ.get("SHION_DATA_ROOT", DEFAULT_DATA_ROOT))
        root = raw.expanduser().resolve(strict=False)
        if not root.is_absolute():
            raise ValueError("SHION_DATA_ROOT must be absolute")
        return cls(root)

    @property
    def models(self) -> Path: return self.root / "models"
    @property
    def conversation_models(self) -> Path: return self.models / "conversation"
    @property
    def voice_models(self) -> Path: return self.models / "voice"
    @property
    def data(self) -> Path: return self.root / "data"
    @property
    def conversation_db(self) -> Path: return self.data / "conversations" / "shion_chat.db"
    @property
    def artifacts(self) -> Path: return self.root / "artifacts"
    @property
    def voice_artifacts(self) -> Path: return self.artifacts / "voice"
    @property
    def image_artifacts(self) -> Path: return self.artifacts / "images"
    @property
    def attachments(self) -> Path: return self.artifacts / "attachments"
    @property
    def exports(self) -> Path: return self.artifacts / "exports"
    @property
    def cache(self) -> Path: return self.root / "cache"
    @property
    def huggingface_cache(self) -> Path: return self.cache / "huggingface"
    @property
    def temp(self) -> Path: return self.root / "temp"
    @property
    def logs(self) -> Path: return self.root / "logs"

    def create_runtime_dirs(self) -> None:
        for path in (self.data / "conversations", self.artifacts, self.voice_artifacts,
                     self.image_artifacts, self.attachments, self.exports, self.cache,
                     self.huggingface_cache, self.temp, self.logs):
            path.mkdir(parents=True, exist_ok=True)

    def within(self, candidate: Path, parent: Path) -> bool:
        try:
            candidate.resolve(strict=False).relative_to(parent.resolve(strict=False))
            return True
        except ValueError:
            return False
