from __future__ import annotations

import json
from pathlib import Path


PUBLIC_MODEL_FIELDS = (
    "display_name", "repo_id", "revision", "parent_model", "base_origin",
    "provenance", "modification_type", "parameter_scale", "available",
    "unavailable_reason",
)


class ModelRegistry:
    """Server-side allowlist. Local paths are never accepted from the client."""

    def __init__(self, specs: dict) -> None:
        self.specs = specs

    @classmethod
    def from_file(cls, path: Path) -> "ModelRegistry":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def available(self, alias: str) -> dict:
        spec = self.specs.get(alias)
        if spec is None or not spec.get("available"):
            raise ValueError("model alias is not available")
        return spec

    def public_models(self) -> list[dict]:
        return [
            {"alias": alias, **{key: spec[key] for key in PUBLIC_MODEL_FIELDS if key in spec}}
            for alias, spec in self.specs.items()
        ]
