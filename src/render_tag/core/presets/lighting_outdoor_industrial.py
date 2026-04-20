"""Preset: ``lighting.outdoor_industrial`` — very bright, hard-shadow outdoor sun."""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.outdoor_industrial",
    description="Outdoor sun: very bright, hard shadows.",
)
def lighting_outdoor_industrial() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 800.0,
                "intensity_max": 1200.0,
                "radius_min": 0.0,
                "radius_max": 0.02,
                "directional": [],
            }
        }
    }
