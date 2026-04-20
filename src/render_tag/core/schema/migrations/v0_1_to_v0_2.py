"""v0.1 -> v0.2: polymorphic subject architecture.

v0.2 introduces ``scenario.subject`` as a discriminated union of TAGS/BOARD.
Configs produced before v0.2 carry flat fields on ``tag.*`` and ``scenario.*``
(``tag_families``, ``tag_size``, ``tags_per_scene``, ``layout``, ...). This
migration synthesizes ``scenario.subject`` from those fields when it is
missing.

BOARD configs are left alone here — ``ScenarioConfig`` handles them via the
field-map path. This is intentional: BOARD subject synthesis requires
``grid_size`` / ``marker_size``, which may still be absent at this stage for
configs that set ``layout: board`` without specifying geometry.
"""

from __future__ import annotations

from typing import Any

from render_tag.core.schema.legacy._warn import warn_legacy

FROM_VERSION = "0.1"
TO_VERSION = "0.2"


def apply(data: dict[str, Any]) -> dict[str, Any]:
    upgraded = data.copy()
    upgraded["version"] = TO_VERSION

    # Synthesize scenario.subject from legacy fields when missing. tag.size_meters
    # and tag.family must be honored even when scenario has no tag_families /
    # tags_per_scene — otherwise a config with only tag: {size_meters: 0.16}
    # silently defaults to 0.1 m via Pydantic's default_factory.
    scenario = upgraded.setdefault("scenario", {})
    if not isinstance(scenario, dict):
        return upgraded
    raw_tag = upgraded.get("tag")
    tag_section: dict[str, Any] = raw_tag if isinstance(raw_tag, dict) else {}

    if "subject" in scenario:
        return upgraded

    # Legacy BOARD subject: leave alone, ScenarioConfig handles defaults.
    if scenario.get("layout") == "board" or "board" in scenario:
        return upgraded

    has_scenario_tag_fields = "tag_families" in scenario or "tags_per_scene" in scenario
    has_tag_section_fields = "family" in tag_section or "size_meters" in tag_section
    if not (has_scenario_tag_fields or has_tag_section_fields):
        return upgraded

    tag_families = scenario.pop("tag_families", None)
    if tag_families is not None:
        warn_legacy("scenario.tag_families", "scenario.subject.tag_families")
    else:
        family = tag_section.get("family", "tag36h11")
        if "family" in tag_section:
            warn_legacy("tag.family", "scenario.subject.tag_families")
        tag_families = [family] if not isinstance(family, list) else family

    tags_per_scene = scenario.pop("tags_per_scene", None)
    if tags_per_scene is not None:
        warn_legacy("scenario.tags_per_scene", "scenario.subject.tags_per_scene")
        if isinstance(tags_per_scene, (list, tuple)) and len(tags_per_scene) > 0:
            tags_per_scene = tags_per_scene[-1]
    else:
        tags_per_scene = 10

    size_meters = scenario.pop("tag_size", None)
    if size_meters is not None:
        warn_legacy("scenario.tag_size", "scenario.subject.size_mm")
    else:
        if "size_meters" in tag_section:
            warn_legacy("tag.size_meters", "scenario.subject.size_mm")
        size_meters = tag_section.get("size_meters", 0.1)

    scenario["subject"] = {
        "type": "TAGS",
        "tag_families": tag_families,
        "size_mm": float(size_meters) * 1000.0,
        "tags_per_scene": tags_per_scene,
    }

    return upgraded
