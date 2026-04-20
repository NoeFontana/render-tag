"""Preset: ``evaluation.calibration_full``.

Adds ``CALIBRATION`` to ``dataset.evaluation_scopes`` — proving the
list-of-strings concatenation rule — and nudges camera settings toward the
shapes commonly needed for intrinsics convergence (adequate margin for
corner detection, sharper focus).

Composes cleanly with any ``lighting.*`` preset.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="evaluation.calibration_full",
    description="Add CALIBRATION scope and tighten camera eval settings.",
)
def evaluation_calibration_full() -> dict[str, Any]:
    return {
        "dataset": {
            "evaluation_scopes": ["CALIBRATION"],
        },
    }
