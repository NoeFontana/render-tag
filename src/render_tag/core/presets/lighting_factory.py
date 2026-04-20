"""Preset: ``lighting.factory`` — bright diffuse factory-floor lighting."""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.factory",
    description="Factory floor: bright diffuse light, soft shadows.",
)
def lighting_factory() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 200.0,
                "intensity_max": 400.0,
                "radius_min": 0.1,
                "radius_max": 0.5,
                "directional": [],
            }
        }
    }
