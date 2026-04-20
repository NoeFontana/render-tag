"""Preset: ``locus.v1_baseline``.

The shared rig, tag material, scenario, scene, and evaluation shape used by
every ``locus_v1`` benchmark. List this preset first in any ``presets:`` list
— scenario-specific presets (``sensor.*``, ``lighting.*``, ``shadow.*``) are
expected to compose on top and win on conflicting fields (ISO, tone mapping,
scene.lighting).

Semantics to know before editing:

- ``dataset.evaluation_scopes`` is a ``list[str]``. Under ``deep_merge`` it
  extends-and-dedupes, so consumers can add scopes but cannot *remove* the
  bundled ``detection`` / ``pose_estimation`` entries. This matches every
  locus_v1 benchmark's needs today; drop this field from the preset if a
  future benchmark needs a strict subset.
- ``scene.lighting`` values match the "default locus_v1" lighting that 4 of
  the 7 original YAMLs inlined verbatim. ``lighting.low_key``,
  ``lighting.outdoor_industrial`` etc. override this when composed later.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="locus.v1_baseline",
    description="Locus V1 shared rig, tag material, scenario, scene, eval scopes.",
    version="1.0",
)
def locus_v1_baseline() -> dict[str, Any]:
    return {
        "dataset": {
            "evaluation_scopes": ["detection", "pose_estimation"],
        },
        "camera": {
            "resolution": [1920, 1080],
            "fov": 70.0,
            "samples_per_scene": 1,
            "min_distance": 0.5,
            "max_distance": 8.0,
            "min_elevation": 0.5,
            "max_elevation": 1.0,
            "min_roll": -180.0,
            "max_roll": 180.0,
            "ppm_constraint": {
                "min": 5.0,
                "max": 40.0,
                "distribution": "uniform",
            },
        },
        "tag": {
            "margin_bits": 1,
            "material": {
                "randomize": True,
                "roughness_min": 0.4,
                "roughness_max": 0.8,
                "specular_min": 0.1,
                "specular_max": 0.3,
            },
        },
        "scenario": {
            "sampling_mode": "random",
            "use_board": False,
        },
        "scene": {
            "lighting": {
                "intensity_min": 100.0,
                "intensity_max": 1000.0,
                "radius_min": 0.2,
                "radius_max": 0.2,
                "directional": [],
            },
            "texture_dir": "assets/textures/background",
            "texture_scale_min": 0.1,
            "texture_scale_max": 20.0,
        },
    }
