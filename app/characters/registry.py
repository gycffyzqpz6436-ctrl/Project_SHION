from __future__ import annotations

import json
from pathlib import Path


class CharacterRegistry:
    """Read-only registry for Owner-approved Character profiles and asset sets."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def get(self, character_id: str) -> dict:
        if not character_id.isascii() or not character_id.replace("_", "").isalnum():
            raise KeyError(character_id)
        profile_path = self.root / character_id / "profile.json"
        if not profile_path.is_file():
            raise KeyError(character_id)
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if profile.get("character_id") != character_id:
            raise ValueError("character profile identity mismatch")
        manifest_path = (profile_path.parent / profile["renderer"]["manifest"]).resolve()
        if self.root not in manifest_path.parents or not manifest_path.is_file():
            raise ValueError("character manifest path is invalid")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("owner_approved") or manifest.get("character_id") != character_id:
            raise ValueError("character asset set is not Owner-approved")
        base = "/assets/characters/" + manifest_path.parent.relative_to(self.root).as_posix() + "/"
        assets = {role: base + item["path"] for role, item in manifest["assets"].items()}
        return {**profile, "assets": assets, "asset_set": {"id": manifest["asset_set_id"], "version": manifest["version"], "status": manifest["status"]}, "presentation_states": manifest.get("presentation_states", {})}

    def list(self) -> list[dict]:
        results = []
        for profile_path in sorted(self.root.glob("*/profile.json")):
            profile = self.get(profile_path.parent.name)
            results.append(profile)
        return results
