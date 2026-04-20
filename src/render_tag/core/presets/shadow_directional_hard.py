"""Preset: ``shadow.directional_hard``.

Injects one SUN overlay at a fixed azimuth/elevation. Composes on top of any
``lighting.*`` preset so the ambient intensity range still comes from that
layer while the SUN carves the physically correct shadow-edge contrast.

The fixed azimuth is overridden in ``configs/experiments/locus_shadow_azimuth.yaml``
and benchmark configs can pin worst-case angles once characterization lands.

Note: a bare SUN without sky fill produces unnaturally black shadows. The
repo ships only ``assets/hdri/dummy.exr``, so this preset leaves
``background_hdri`` unset — configs that want realistic sky fill should point
``scene.background_hdri`` at a real HDRI.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="shadow.directional_hard",
    description="Directional SUN overlay for physically correct hard-shadow stress.",
)
def shadow_directional_hard() -> dict[str, Any]:
    return {
        "scene": {
            "lighting": {
                "directional": {
                    "azimuth": 0.785398,
                    "elevation": 0.3,
                    "intensity": 5.0,
                }
            }
        }
    }
