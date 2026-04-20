"""Preset: ``lighting.mixed_temperature``.

Two directional sources at distinct color temperatures — warm tungsten
(~3000K approximation) opposing cool daylight (~6500K approximation). The
tag surface receives different-spectrum light per facet, which defeats
adaptive-thresholding detectors that assume uniform illumination.

Non-parametric: fixed azimuths so the per-scene variance comes from camera
pose, not lighting geometry. If you want to sweep the temperature delta,
override ``scene.lighting.directional[*].color`` at the config level.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.mixed_temperature",
    description="Opposing warm+cool directional sources to stress adaptive thresholding.",
)
def lighting_mixed_temperature() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "intensity_min": 30.0,
                "intensity_max": 120.0,
                "directional": [
                    {
                        "azimuth": 0.0,
                        "elevation": 0.4,
                        "intensity": 3.0,
                        "color": [1.0, 0.7, 0.4],
                    },
                    {
                        "azimuth": 3.141593,
                        "elevation": 0.4,
                        "intensity": 3.0,
                        "color": [0.8, 0.9, 1.0],
                    },
                ],
            }
        }
    }
