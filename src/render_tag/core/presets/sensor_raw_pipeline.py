"""Preset: ``sensor.raw_pipeline``.

Pre-ISP raw-sensor profile: linear tone mapping and a stacked Poisson (shot) +
Gaussian (read) noise pipeline. Models what a detector sees when running
directly on Bayer or pre-demosaic output for latency reasons — a common
perception-team request once latency budgets tighten.

Note: ``iso_coupling`` is disabled so the preset's sensor_noise list is not
overwritten by the ISO-coupling synthesizer. Users override ``iso`` on top to
stress the gain stage independently.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="sensor.raw_pipeline",
    description="Pre-ISP raw-sensor: linear tonemap + stacked Poisson + Gaussian noise.",
)
def sensor_raw_pipeline() -> dict[str, Any]:
    return {
        "camera": {
            "tone_mapping": "linear",
            "iso": 1600,
            "iso_coupling": False,
            "sensor_noise": {
                "models": [
                    {"model": "poisson", "scale": 1000.0},
                    {"model": "gaussian", "stddev": 0.004},
                ]
            },
        }
    }
