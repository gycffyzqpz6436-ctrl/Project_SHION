"""Isolated image-generation boundary for future SHION orchestration.

This package intentionally does not enable image generation in the web UI.
"""

from .spec import ImageGenerationRequest, ShionVisualSpec

__all__ = ["ImageGenerationRequest", "ShionVisualSpec"]
