from __future__ import annotations

from .spec import ShionVisualSpec


QUALITY_TAGS = ("masterpiece", "high score", "great score", "absurdres")
MAX_PROMPT_CHARS = 380
NEGATIVE_TAGS = (
    "lowres",
    "bad anatomy",
    "bad hands",
    "missing fingers",
    "extra digits",
    "fewer digits",
    "text",
    "signature",
    "watermark",
    "blurry",
    "low score",
    "bad score",
)


def build_animagine_prompt(spec: ShionVisualSpec) -> tuple[str, str]:
    """Convert a model-neutral spec to Animagine's tag-oriented prompt."""

    tags = [
        "1girl",
        "solo",
        "mature adult woman",
        "original character",
        "safe",
        "2d anime",
        spec.style,
        spec.subject,
        *spec.appearance,
        *spec.clothing,
        spec.expression,
        spec.pose,
        spec.background,
        spec.lighting,
        spec.safety,
    ]
    if spec.hands_visible:
        tags.extend(("hands visible", "five fingers where visible", "detailed hands"))
    # CLIP has a 77-token window. Preserve the most important subject/control
    # tags and always reserve space for the model's quality tags.
    selected: list[str] = []
    quality_text = ", ".join(QUALITY_TAGS)
    for tag in (tag for tag in tags if tag):
        proposed = ", ".join((*selected, tag, quality_text))
        if len(proposed) > MAX_PROMPT_CHARS:
            continue
        selected.append(tag)
    selected.extend(QUALITY_TAGS)
    return ", ".join(selected), ", ".join(NEGATIVE_TAGS)
