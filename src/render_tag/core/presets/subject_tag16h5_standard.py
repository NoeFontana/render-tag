"""Preset: ``subject.tag16h5_standard``.

Smaller tag family sibling of ``subject.tag36h11_standard``: same 160 mm
single-tag layout but the lower-density tag16h5 family with a matching 16 px
minimum (tag16h5 encodes fewer bits, so the detector's pixel floor is
proportionally smaller).
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="subject.tag16h5_standard",
    description="Standard locus_v1 subject: one 160 mm tag16h5, min 16 px.",
    version="1.0",
)
def subject_tag16h5_standard() -> dict[str, Any]:
    return {
        "camera": {"min_tag_pixels": 16},
        "scenario": {
            "subject": {
                "type": "TAGS",
                "tag_families": ["tag16h5"],
                "size_mm": 160.0,
                "tags_per_scene": 1,
            },
        },
    }
