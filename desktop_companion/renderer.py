from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path


class CharacterRenderer(ABC):
    @abstractmethod
    def set_character(self, character_id: str) -> None: ...
    @abstractmethod
    def set_state(self, state: str) -> None: ...
    @abstractmethod
    def set_scale(self, scale: float) -> None: ...
    @abstractmethod
    def show(self) -> None: ...
    @abstractmethod
    def hide(self) -> None: ...


class Static2DAsset:
    def __init__(self, repository_root: Path, role: str = "panel") -> None:
        self.root = repository_root.resolve() / "app" / "static" / "assets" / "characters" / "shion"
        profile = json.loads((self.root / "profile.json").read_text(encoding="utf-8"))
        if profile["character_id"] != "shion" or profile["renderer"]["type"] != "static_2d":
            raise ValueError("SHION profile does not declare Static2D")
        manifest_path = (self.root / profile["renderer"]["manifest"]).resolve()
        if self.root not in manifest_path.parents: raise ValueError("unsafe character manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["asset_set_id"] != profile["renderer"]["asset_set"] or not manifest.get("owner_approved"):
            raise ValueError("character asset is not Owner-approved")
        item = manifest["assets"][role]
        self.path = (manifest_path.parent / item["path"]).resolve()
        if manifest_path.parent not in self.path.parents or hashlib.sha256(self.path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Official SHION asset integrity failure")
        self.character_id, self.role, self.manifest = "shion", role, manifest


class Static2DRenderer(CharacterRenderer):
    STATES = {"IDLE", "GENERATING", "WAITING_FOR_GPU", "SPEAKING", "OFFLINE", "ERROR"}

    def __init__(self, window, label, repository_root: Path, scale: float = .34) -> None:
        import tkinter as tk
        self.tk, self.window, self.label = tk, window, label
        self.asset = Static2DAsset(repository_root)
        self.character_id, self.state, self.scale, self.image = "shion", "IDLE", scale, None
        self._render()

    def _render(self) -> None:
        source = self.tk.PhotoImage(file=str(self.asset.path))
        divisor = max(1, round(1 / self.scale))
        self.image = source.subsample(divisor, divisor)
        self.label.configure(image=self.image)

    def set_character(self, character_id: str) -> None:
        if character_id != "shion": raise ValueError("Phase H supports SHION only")
        self.character_id = character_id

    def set_state(self, state: str) -> None:
        if state not in self.STATES: raise ValueError("invalid renderer state")
        self.state = state

    def set_scale(self, scale: float) -> None:
        if not .2 <= scale <= .8: raise ValueError("invalid renderer scale")
        self.scale = scale; self._render()

    def show(self) -> None: self.window.deiconify()
    def hide(self) -> None: self.window.withdraw()
