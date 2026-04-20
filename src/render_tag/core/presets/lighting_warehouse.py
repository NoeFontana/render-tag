"""Preset: ``lighting.warehouse`` — dim lighting with slightly harder shadows."""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.warehouse",
    description="Warehouse: dim light, slightly harder shadows.",
)
def lighting_warehouse() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 50.0,
                "intensity_max": 200.0,
                "radius_min": 0.05,
                "radius_max": 0.2,
                "directional": [],
            }
        }
    }
