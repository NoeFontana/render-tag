"""Preset: ``sensor.industrial_dr``.

Low-dynamic-range industrial-camera profile. Compose with an outdoor lighting
preset (``lighting.outdoor_industrial``) and a harsh-shadow preset
(``shadow.harsh``) to reproduce the canonical deployment failure mode: tag in
hard shade, crushed into the noise floor, unrecoverable.

Composes cleanly with ``sensor.hdr_sweep`` — users can override ``iso`` on top
when the characterization sweep picks a harsher stress value.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="sensor.industrial_dr",
    description="Low-DR industrial sensor: 60 dB dynamic range, linear tone mapping.",
)
def sensor_industrial_dr() -> dict[str, Any]:
    return {
        "camera": {
            "dynamic_range_db": 60.0,
            "tone_mapping": "linear",
            "iso": 400,
            "iso_coupling": True,
        }
    }
