from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ShionVisualSpec:
    """Model-neutral visual intent produced by the future conversation layer."""

    subject: str
    adult: bool = True
    style: str = "clean 2D anime illustration"
    appearance: tuple[str, ...] = ()
    clothing: tuple[str, ...] = ()
    expression: str = "natural expression"
    pose: str = "simple standing pose"
    background: str = "simple background"
    lighting: str = "soft cinematic lighting"
    hands_visible: bool = False
    safety: str = "safe, non-sexual"


@dataclass(frozen=True)
class ImageGenerationRequest:
    visual_spec: ShionVisualSpec
    output_path: Path
    width: int = 1024
    height: int = 1024
    steps: int = 28
    cfg: float = 5.0
    seed: int = 20260810
    reference_images: tuple[Path, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.visual_spec.adult:
            raise ValueError("image runtime accepts adult-character requests only")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if self.steps < 1 or self.steps > 100:
            raise ValueError("steps must be between 1 and 100")
        if self.output_path.suffix.lower() not in {".png", ".webp"}:
            raise ValueError("output must be PNG or WebP")
