"""Preset: ``subject.tag36h11_standard``.

The canonical tag36h11 single-tag subject used by locus_v1 benchmarks:
one 160 mm tag per scene, min-pixels gate at 36.

``camera.min_tag_pixels`` is bundled here (not under ``scenario.subject``)
because today's YAMLs write it at ``camera.min_tag_pixels``; keeping the
override target stable avoids silent path-drift during merge.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.presets.base import register_preset


@register_preset(
    name="subject.tag36h11_standard",
    description="Standard locus_v1 subject: one 160 mm tag36h11, min 36 px.",
    version="1.0",
)
def subject_tag36h11_standard() -> dict[str, Any]:
    return {
        "camera": {"min_tag_pixels": 36},
        "scenario": {
            "subject": {
                "type": "TAGS",
                "tag_families": ["tag36h11"],
                "size_mm": 160.0,
                "tags_per_scene": 1,
            },
        },
    }
