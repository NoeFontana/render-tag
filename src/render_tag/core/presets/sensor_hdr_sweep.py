"""Preset: ``sensor.hdr_sweep`` (scaffold).

Intended to exercise a wide dynamic-range sweep on the sensor simulation
(exposure/ISO/noise). Concrete override values depend on the sensor-config
knobs the user wants to vary; this scaffold reserves the name and emits an
empty override so composition remains a no-op until filled in.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="sensor.hdr_sweep",
    description="Sweep sensor dynamic range (exposure/ISO/noise).",
)
def sensor_hdr_sweep() -> dict[str, Any]:
    return {}
