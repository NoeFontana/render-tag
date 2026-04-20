"""Declarative table of deprecated field → current field rewrites.

Each entry in :data:`LEGACY_FIELDS` represents one deprecation with explicit
sunset metadata. Runs after the versioned migration chain in
``adapt_config`` — at this point the config has the current schema's overall
shape, but may still carry leftover legacy field names.

Entries carry ``since`` and ``removed_in`` as package versions (from
``pyproject.toml``), not schema versions. A test in
``tests/unit/core_logic/test_legacy_sunset.py`` fails the build when the
current package version reaches any ``removed_in``, forcing either removal
or a conscious deadline extension.

The one-shot nature of this list is intentional. Unlike versioned migrations
(which are append-only forever), every row here is a sunset candidate. If a
row has been in the table for multiple minor releases, the right answer is
usually to delete it — not extend the deadline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from render_tag.core.schema.legacy._warn import warn_legacy


@dataclass(frozen=True)
class LegacyEntry:
    """One deprecated-field rewrite with sunset metadata.

    Attributes:
        path: Dotted identifier of the legacy field (for diagnostics and the
            sunset test). Not interpreted by ``apply_all``.
        replacement: Dotted identifier of the replacement field.
        since: Package version where the deprecation was first surfaced.
        removed_in: Package version where the entry must be gone.
        apply: Function that mutates ``data`` in place, returning it. Emits
            a ``DeprecationWarning`` via ``warn_legacy`` when the legacy
            field is encountered.
    """

    path: str
    replacement: str
    since: str
    removed_in: str
    apply: Callable[[dict[str, Any]], dict[str, Any]]


# --- Transform implementations ---------------------------------------------


def _apply_intent_to_evaluation_scopes(data: dict[str, Any]) -> dict[str, Any]:
    dataset = data.get("dataset")
    if not isinstance(dataset, dict) or "intent" not in dataset:
        return data
    warn_legacy("dataset.intent", "dataset.evaluation_scopes")
    intent_val = dataset.pop("intent")
    if "evaluation_scopes" in dataset:
        return data
    if intent_val == "calibration":
        dataset["evaluation_scopes"] = ["CALIBRATION"]
    elif "pose" in str(intent_val):
        dataset["evaluation_scopes"] = [
            "DETECTION",
            "POSE_ACCURACY",
            "CORNER_PRECISION",
        ]
    return data


def _apply_seed_to_seeds_global(data: dict[str, Any]) -> dict[str, Any]:
    dataset = data.get("dataset")
    if not isinstance(dataset, dict) or "seed" not in dataset:
        return data
    if "seeds" not in dataset:
        dataset["seeds"] = {}
    if isinstance(dataset["seeds"], dict) and "global_seed" not in dataset["seeds"]:
        dataset["seeds"]["global_seed"] = dataset.pop("seed")
    return data


def _make_tag_strip(field: str, replacement: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _apply(data: dict[str, Any]) -> dict[str, Any]:
        tag = data.get("tag")
        if not isinstance(tag, dict) or field not in tag:
            return data
        warn_legacy(f"tag.{field}", replacement)
        tag.pop(field)
        return data

    return _apply


def _apply_sensor_dynamics(data: dict[str, Any]) -> dict[str, Any]:
    """Collapse flat camera.* sensor fields into nested camera.sensor_dynamics.

    Handles several legacy fields as one unit because they all belong to the
    same restructured sub-section. Sunset as a group.
    """
    camera = data.get("camera")
    if not isinstance(camera, dict):
        return data
    dynamics = camera.get("sensor_dynamics", {})
    if not isinstance(dynamics, dict):
        return data

    for field in ("velocity_mean", "velocity_std", "shutter_time_ms"):
        if field in camera and field not in dynamics:
            dynamics[field] = camera.pop(field)

    if "shutter_speed" in camera:
        dynamics["shutter_time_ms"] = camera.pop("shutter_speed") * 1000.0

    if "rolling_shutter_readout" in camera:
        dynamics["rolling_shutter_duration_ms"] = camera.pop("rolling_shutter_readout")

    if dynamics:
        camera["sensor_dynamics"] = dynamics
    return data


def _apply_scenario_board_subject(data: dict[str, Any]) -> dict[str, Any]:
    """Synthesize scenario.subject for legacy BOARD configs.

    The v0.1->v0.2 migration leaves BOARD configs alone (it needs grid/marker
    info that may not yet be present). By the time field_map runs, ScenarioConfig
    shape is known and we can synthesize the BOARD subject safely.

    The TAGS path is handled by the migrator — this entry intentionally does
    not cover it. See ``test_v01_tag_scenario_fields_synthesize_subject`` in
    ``tests/unit/test_schema_adapter.py``.
    """
    scenario = data.get("scenario")
    if not isinstance(scenario, dict) or "subject" in scenario:
        return data
    is_board = scenario.get("layout") == "board" or "board" in scenario
    if not is_board:
        return data
    grid_size = scenario.pop("grid_size", [3, 3])
    scenario["subject"] = {
        "type": "BOARD",
        "rows": grid_size[1],
        "cols": grid_size[0],
        "marker_size": scenario.pop("marker_size", 0.08),
        "dictionary": scenario.pop("tag_family", "tag36h11"),
    }
    if "square_size" in scenario:
        scenario["subject"]["square_size"] = scenario.pop("square_size")
    return data


def _apply_scene_lighting_preset_to_presets(data: dict[str, Any]) -> dict[str, Any]:
    """Rewrite ``scene.lighting_preset: X`` to top-level ``presets: [lighting.X]``.

    The legacy field is prepended to the preset list so any explicit modern
    ``presets: [...]`` the user also wrote composes *after* and wins. Emits
    a single ``DeprecationWarning`` per encounter.
    """
    scene = data.get("scene")
    if not isinstance(scene, dict) or "lighting_preset" not in scene:
        return data
    value = scene.pop("lighting_preset")
    if value is None:
        return data
    value_str = value.value if hasattr(value, "value") else str(value)
    preset_name = f"lighting.{value_str}"
    warn_legacy("scene.lighting_preset", f"presets: [{preset_name}]")
    existing = data.get("presets")
    if existing is None:
        data["presets"] = [preset_name]
    elif isinstance(existing, list):
        if preset_name not in existing:
            existing.insert(0, preset_name)
    else:
        raise ValueError("Top-level `presets` must be a list of preset names.")
    return data


def _apply_scenario_layout_strip(data: dict[str, Any]) -> dict[str, Any]:
    scenario = data.get("scenario")
    if not isinstance(scenario, dict) or "layout" not in scenario:
        return data
    warn_legacy("scenario.layout", "scenario.subject.type")
    scenario.pop("layout")
    return data


# --- Registry ---------------------------------------------------------------


LEGACY_FIELDS: list[LegacyEntry] = [
    LegacyEntry(
        path="dataset.intent",
        replacement="dataset.evaluation_scopes",
        since="0.6",
        removed_in="1.0",
        apply=_apply_intent_to_evaluation_scopes,
    ),
    LegacyEntry(
        path="dataset.seed",
        replacement="dataset.seeds.global_seed",
        since="0.6",
        removed_in="1.0",
        apply=_apply_seed_to_seeds_global,
    ),
    LegacyEntry(
        path="tag.family",
        replacement="scenario.subject.tag_families",
        since="0.7",
        removed_in="1.0",
        apply=_make_tag_strip("family", "scenario.subject.tag_families"),
    ),
    LegacyEntry(
        path="tag.size_meters",
        replacement="scenario.subject.size_mm",
        since="0.7",
        removed_in="1.0",
        apply=_make_tag_strip("size_meters", "scenario.subject.size_mm"),
    ),
    LegacyEntry(
        path="tag.size_mm",
        replacement="scenario.subject.size_mm",
        since="0.7",
        removed_in="1.0",
        apply=_make_tag_strip("size_mm", "scenario.subject.size_mm"),
    ),
    LegacyEntry(
        path="camera.sensor_dynamics.*",
        replacement="camera.sensor_dynamics.*",
        since="0.6",
        removed_in="1.0",
        apply=_apply_sensor_dynamics,
    ),
    LegacyEntry(
        path="scenario.layout(=board)",
        replacement="scenario.subject (BOARD)",
        since="0.7",
        removed_in="1.0",
        apply=_apply_scenario_board_subject,
    ),
    LegacyEntry(
        path="scenario.layout",
        replacement="scenario.subject.type",
        since="0.7",
        removed_in="1.0",
        apply=_apply_scenario_layout_strip,
    ),
    LegacyEntry(
        path="scene.lighting_preset",
        replacement="presets: [lighting.X]",
        since="0.9",
        removed_in="1.0",
        apply=_apply_scene_lighting_preset_to_presets,
    ),
]


def apply_all(data: dict[str, Any]) -> dict[str, Any]:
    """Walk the LEGACY_FIELDS table and apply each entry in order."""
    for entry in LEGACY_FIELDS:
        data = entry.apply(data)
    return data
