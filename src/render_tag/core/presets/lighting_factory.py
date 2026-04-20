"""Preset: ``lighting.factory``.

Mirrors ``LightingPreset.FACTORY`` via ``get_lighting_preset`` so the
legacy ``scene.lighting_preset: factory`` path produces a bit-identical
resolved config when rewritten by the ACL.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.config import LightingPreset, get_lighting_preset
from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.factory",
    description="Factory floor: bright diffuse light, soft shadows.",
)
def lighting_factory() -> dict[str, Any]:
    lighting = get_lighting_preset(LightingPreset.FACTORY)
    return {"scene": {"lighting": lighting.model_dump()}}
