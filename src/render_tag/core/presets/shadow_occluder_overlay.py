"""Preset: ``shadow.occluder_overlay`` — enables shadow-casting occluder plates.

Pair with ``lighting.outdoor_sun`` (or any preset that emits a SUN) so the
plate edges project onto the tag plane and stress corner detectors against
hard-edged shadow boundaries (edge / corner / slit patterns).
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="shadow.occluder_overlay",
    description="Cast half-plane plate shadows (edge/corner/slit) across the tag plane.",
)
def shadow_occluder_overlay() -> dict[str, Any]:
    return {
        "scenario": {
            "occluders": {
                "enabled": True,
                "patterns": ["edge", "corner", "slit"],
                "plate_size_m": 0.5,
                "plate_thickness_m": 0.005,
                "height_min_m": 0.05,
                "height_max_m": 0.20,
                "edge_offset_max_m": 0.03,
                "slit_width_min_m": 0.005,
                "slit_width_max_m": 0.030,
                "albedo": 0.05,
                "roughness": 0.9,
            }
        }
    }
