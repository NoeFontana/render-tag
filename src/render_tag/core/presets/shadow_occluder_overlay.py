"""Preset: ``shadow.occluder_overlay`` — enables shadow-casting occluders.

Pair with ``lighting.outdoor_sun`` (or any preset that emits a SUN) so the
occluder umbra crosses the tag plane and stresses corner detectors against
hard-edged shadow boundaries.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="shadow.occluder_overlay",
    description="Place rod occluders along the SUN ray so their umbra crosses the tag.",
)
def shadow_occluder_overlay() -> dict[str, Any]:
    return {
        "scenario": {
            "occluders": {
                "enabled": True,
                "count_min": 1,
                "count_max": 3,
                "shape": "rod",
                "width_m": 0.003,
                "length_m": 0.15,
                "offset_min_m": 0.01,
                "offset_max_m": 0.04,
                "lateral_jitter_m": 0.02,
                "albedo": 0.05,
                "roughness": 0.9,
            }
        }
    }
