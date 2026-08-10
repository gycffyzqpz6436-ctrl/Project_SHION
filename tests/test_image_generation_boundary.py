import json
from pathlib import Path

import pytest

from app.tools.image_generation.prompt_builder import build_animagine_prompt
from app.tools.image_generation.spec import ImageGenerationRequest, ShionVisualSpec


ROOT = Path(__file__).parents[1]


def test_model_registry_is_default_deny_and_pinned() -> None:
    registry = json.loads(
        (ROOT / "app/tools/image_generation/model_registry.json").read_text(encoding="utf-8")
    )
    assert registry["active_model"] is None
    model = registry["models"]["animagine-xl-4.0-opt"]
    assert len(model["revision"]) == 40
    assert model["trust_remote_code"] is False
    assert model["local_path"].startswith("D:/AI/Project_SHION/models/image/")


def test_prompt_builder_translates_visual_spec_to_tags() -> None:
    spec = ShionVisualSpec(
        subject="violet-haired woman",
        clothing=("black china dress", "high heels"),
        hands_visible=True,
    )
    prompt, negative = build_animagine_prompt(spec)
    assert "mature adult woman" in prompt
    assert "black china dress" in prompt
    assert "masterpiece" in prompt
    assert len(prompt) <= 380
    assert "bad hands" in negative


def test_request_rejects_non_adult_character() -> None:
    request = ImageGenerationRequest(
        ShionVisualSpec(subject="character", adult=False), Path("result.png")
    )
    with pytest.raises(ValueError, match="adult-character"):
        request.validate()
