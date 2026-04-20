"""Preset: ``lighting.low_key``.

Low-intensity, single grazing directional source. Designed to compose with
``sensor.industrial_dr`` (60 dB dynamic range, linear tone mapping) so the
shadow side of the tag falls below the sensor's noise floor and clips to
black — the "robot in a dim aisle with one fluorescent overhead" failure
mode that HDR-envelope sensors mask but low-DR industrial sensors cannot.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.low_key",
    description="Low-intensity grazing light for clip-to-black stress (compose with sensor.industrial_dr).",  # noqa: E501
)
def lighting_low_key() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 20.0,
                "intensity_max": 80.0,
                "radius_min": 0.05,
                "radius_max": 0.15,
                "directional": {
                    "azimuth": 1.570796,
                    "elevation": 0.2,
                    "intensity": 2.0,
                },
            },
            "background_hdri": None,
        }
    }
