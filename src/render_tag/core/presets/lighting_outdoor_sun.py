"""Preset: ``lighting.outdoor_sun`` — real outdoor sun with low ambient fill.

Models the dominant-SUN regime where shaded regions can crush to black on a
low-DR sensor. Distinct from ``lighting.outdoor_industrial`` (which keeps a
brighter ambient floor for general industrial scenes).

Hard cast shadows on tags require an occluder in the scene; pair with
``shadow.occluder_overlay``.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.outdoor_sun",
    description="Real outdoor sun: dim ambient, dominant SUN, hard-shadow capable.",
)
def lighting_outdoor_sun() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 50.0,
                "intensity_max": 200.0,
                "radius_min": 0.0,
                "radius_max": 0.0,
                "directional": [
                    {
                        "azimuth": 0.785398,
                        "elevation": 0.45,
                        "intensity": 30.0,
                    }
                ],
            }
        }
    }
