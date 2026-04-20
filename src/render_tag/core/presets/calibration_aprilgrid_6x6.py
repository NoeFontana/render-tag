"""Preset: ``calibration.aprilgrid_6x6``.

The standard 6x6 tag36h11 AprilGrid board topology shared by every
aprilgrid_* calibration benchmark: golden baseline, Kalibr motion-blur,
Brown-Conrady distortion, Kannala-Brandt fisheye.

Bundles only the fields that are *actually* shared across all four:

- 6x6 board, tag36h11 dictionary, 0.3 spacing_ratio (Kalibr standard).
- BOARD subject type.

``marker_size_mm`` stays per-benchmark (100 mm for golden/distortion, 80 mm
for Kalibr). Likewise for camera rig (FOV, distance, elevation) and
renderer quality — each distortion benchmark tunes those for its scenario.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="calibration.aprilgrid_6x6",
    description="Standard 6x6 tag36h11 AprilGrid board (Kalibr 0.3 spacing).",
    version="1.0",
)
def calibration_aprilgrid_6x6() -> dict[str, Any]:
    return {
        "scenario": {
            "subject": {
                "type": "BOARD",
                "rows": 6,
                "cols": 6,
                "dictionary": "tag36h11",
                "spacing_ratio": 0.3,
            },
        },
    }
