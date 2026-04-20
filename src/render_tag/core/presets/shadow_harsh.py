"""Preset: ``shadow.harsh`` — tight light-source radii for hard shadow edges.

Composes on top of any ``lighting.*`` preset: the lighting preset picks
intensity, ``shadow.harsh`` hardens the shadow by clamping radii.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="shadow.harsh",
    description="Force tight light-source radii for hard shadow edges.",
)
def shadow_harsh() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "radius_min": 0.0,
                "radius_max": 0.02,
            }
        }
    }
