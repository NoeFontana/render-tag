"""Preset: ``lighting.outdoor_industrial`` — bright industrial outdoor with a dominant SUN.

Owns its own ``directional`` SUN so the preset name matches what the recipe
actually emits. Ambient POINT range is reduced from the legacy 800-1200 so a
SUN at intensity 35 is not dwarfed by indirect fill.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.outdoor_industrial",
    description="Bright industrial outdoor: dominant SUN + moderate ambient fill.",
)
def lighting_outdoor_industrial() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 150.0,
                "intensity_max": 400.0,
                "radius_min": 0.0,
                "radius_max": 0.02,
                "directional": [
                    {
                        "azimuth": 0.785398,
                        "elevation": 0.3,
                        "intensity": 35.0,
                    }
                ],
            }
        }
    }
