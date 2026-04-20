"""Preset: ``lighting.warehouse``.

Routes ``LightingPreset.WAREHOUSE`` through the registry for ACL
compatibility.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.config import LightingPreset, get_lighting_preset
from render_tag.core.presets.base import register_preset


@register_preset(
    name="lighting.warehouse",
    description="Warehouse: dim light, slightly harder shadows.",
)
def lighting_warehouse() -> dict[str, Any]:
    lighting = get_lighting_preset(LightingPreset.WAREHOUSE)
    return {"scene": {"lighting": lighting.model_dump()}}
