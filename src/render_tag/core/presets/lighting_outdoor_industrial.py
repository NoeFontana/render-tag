"""Preset: ``lighting.outdoor_industrial``.

Routes ``LightingPreset.OUTDOOR_INDUSTRIAL`` through the registry.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.config import LightingPreset, get_lighting_preset
from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.outdoor_industrial",
    description="Outdoor sun: very bright, hard shadows.",
)
def lighting_outdoor_industrial() -> dict[str, Any]:
    lighting = get_lighting_preset(LightingPreset.OUTDOOR_INDUSTRIAL)
    return {"scene": {"lighting": lighting.model_dump()}}
