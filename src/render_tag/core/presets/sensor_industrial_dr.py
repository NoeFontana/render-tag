"""Preset: ``sensor.industrial_dr``.

Low-dynamic-range industrial-camera profile with a baked-in Gaussian read-noise
floor. Compose with an outdoor lighting preset (``lighting.outdoor_sun``) to
reproduce the canonical deployment failure mode: tag in hard shade, crushed
into the noise floor, unrecoverable.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="sensor.industrial_dr",
    description="Low-DR industrial sensor: 60 dB DR, linear tone mapping, Gaussian read noise.",
)
def sensor_industrial_dr() -> dict[str, Any]:
    return {
        "camera": {
            "dynamic_range_db": 60.0,
            "tone_mapping": "linear",
            "iso": 400,
            "iso_coupling": True,
            "sensor_noise": {
                "model": "gaussian",
                "mean": 0.0,
                "stddev": 0.008,
            },
        }
    }
