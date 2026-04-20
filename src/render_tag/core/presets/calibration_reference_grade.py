"""Preset: ``calibration.reference_grade_rendering``.

Cycles rendering settings tuned for reference-grade calibration targets:
low noise threshold, high sample cap, denoising on. Used by benchmarks
where sub-pixel corner accuracy matters more than render speed
(aprilgrid_golden_v1, aprilgrid_distortion_brown_conrady_v1,
aprilgrid_distortion_kannala_brandt_v1, charuco_golden_v1).

Speed-tuned siblings (aprilgrid_kalibr, charuco_baseline, charuco_opencv)
override these fields inline rather than composing this preset.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="calibration.reference_grade_rendering",
    description="Cycles reference-grade render quality (low noise, 512 samples, denoise).",
    version="1.0",
)
def calibration_reference_grade_rendering() -> dict[str, Any]:
    return {
        "renderer": {
            "mode": "cycles",
            "noise_threshold": 0.01,
            "max_samples": 512,
            "enable_denoising": True,
        },
    }
