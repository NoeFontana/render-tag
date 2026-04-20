"""Preset: ``sensor.hdr_sweep``.

Realistic industrial-camera sensor profile: mid-ISO gain with a parametric
Gaussian read-noise floor. Benchmarks compose this to express "this scene has
non-trivial sensor noise" and can override ``camera.iso`` on top to set the
stress level. Phase 2 can add sibling presets like ``sensor.tonemap_sweep``
without disturbing this one.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="sensor.hdr_sweep",
    description="Realistic industrial sensor: mid-ISO gain with Gaussian read noise.",
)
def sensor_hdr_sweep() -> dict[str, Any]:
    return {
        "camera": {
            "iso": 800,
            "iso_coupling": True,
            "sensor_noise": {
                "model": "gaussian",
                "mean": 0.0,
                "stddev": 0.008,
            },
        }
    }
