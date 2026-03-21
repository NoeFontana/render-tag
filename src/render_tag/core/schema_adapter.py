"""
Anti-Corruption Layer (ACL) for render-tag configuration.

This module handles the translation of legacy configuration formats into
the current v2-compliant internal schema before Pydantic validation.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from render_tag.core.constants import CURRENT_SCHEMA_VERSION
from render_tag.core.logging import get_logger

logger = get_logger(__name__)


def adapt_config(data: dict[str, Any]) -> dict[str, Any]:
    """
    Translates raw legacy dictionaries into modern, v2-compliant dictionaries.

    This is the primary entry point for the Anti-Corruption Layer.
    """
    if data is None:
        return {}

    # 1. Handle flat config format (legacy compatibility)
    # Check if it's flat: look for top-level keys that should be nested
    flat_indicators = {"resolution", "samples", "tag_family", "intent", "seed"}
    is_flat = any(k in data for k in flat_indicators) and "dataset" not in data

    if is_flat:
        data = _convert_flat_config(data)

    # 2. Apply structured schema migrations (v0.0 -> v0.1 -> v0.2)
    # This migration expects a nested structure
    migrator = SchemaMigrator()
    data = migrator.migrate(data)

    # 3. Apply field-level legacy mappings (moved from config.py)
    data = _map_legacy_fields(data)

    return data


class SchemaMigrator:
    """
    Orchestrates sequential migration of schema dictionaries.
    """

    def __init__(self, target_version: str = CURRENT_SCHEMA_VERSION):
        self.target_version = target_version
        # Map of (from_version) -> transformation_function
        self._registry: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "0.0": self._migrate_0_0_to_0_1,
            "0.1": self._migrate_0_1_to_0_2,
        }

    def get_version(self, data: dict[str, Any]) -> str:
        """Extract the version string, defaulting to 0.0 for legacy files."""
        return str(data.get("version", "0.0"))

    def migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sequentially upgrade data until it matches target_version."""
        current_data = data.copy()
        current_version = self.get_version(current_data)

        if current_version == self.target_version:
            return current_data

        # Simple string comparison for now as per spec
        if float(current_version) > float(self.target_version):
            raise ValueError(
                f"Unsupported version: {current_version} (Latest supported: {self.target_version})"
            )

        while current_version != self.target_version:
            transform = self._registry.get(current_version)
            if not transform:
                raise ValueError(f"No migration path found from version {current_version}")

            logger.info(f"Migrating schema: {current_version} -> {self.target_version}")
            current_data = transform(current_data)
            current_version = self.get_version(current_data)

        return current_data

    def upgrade_file_on_disk(self, path: Path | str, migrated_data: dict[str, Any]) -> None:
        """Saves the migrated data back to disk if it was upgraded."""
        path = Path(path)
        if not path.exists():
            return

        logger.warning(f"Upgrading legacy file on disk: {path}")
        if path.suffix.lower() in [".yaml", ".yml"]:
            with open(path, "w") as f:
                yaml.dump(migrated_data, f, sort_keys=False)
        elif path.suffix.lower() == ".json":
            with open(path, "w") as f:
                json.dump(migrated_data, f, indent=2)

    def _migrate_0_0_to_0_1(self, data: dict[str, Any]) -> dict[str, Any]:
        """Base migration: Adds the mandatory version field."""
        upgraded = data.copy()
        upgraded["version"] = "0.1"
        return upgraded

    def _migrate_0_1_to_0_2(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migration to 0.2: Polymorphic Subject Architecture."""
        upgraded = data.copy()
        upgraded["version"] = "0.2"

        if "scenario" in upgraded and isinstance(upgraded["scenario"], dict):
            scenario = upgraded["scenario"]
            if "subject" not in scenario:
                # Staff Engineer: Synchronize tag size from 'tag' section if missing in 'scenario'
                # This prevents defaulting to 0.1m when 0.16m was intended.
                base_tag_size = 0.1
                if "tag" in upgraded and isinstance(upgraded["tag"], dict):
                    base_tag_size = upgraded["tag"].get("size_meters", base_tag_size)

                # Check for legacy fields in scenario to trigger TAGS migration
                if "tag_families" in scenario or "tags_per_scene" in scenario:
                    tag_families = scenario.pop("tag_families", ["tag36h11"])
                    tags_per_scene = scenario.pop("tags_per_scene", 10)

                    # Handle legacy [min, max] tuple often used in early locus-tag configs
                    if isinstance(tags_per_scene, (list, tuple)) and len(tags_per_scene) > 0:
                        tags_per_scene = tags_per_scene[-1]

                    # Override base size if specific tag_size was provided in scenario
                    actual_tag_size = scenario.pop("tag_size", base_tag_size)

                    scenario["subject"] = {
                        "type": "TAGS",
                        "tag_families": tag_families,
                        "size_meters": actual_tag_size,
                        "tags_per_scene": tags_per_scene,
                    }

                # Detect legacy Board config
                elif scenario.get("layout") == "board" or "board" in scenario:
                    # Let ScenarioConfig handle defaults
                    pass

        return upgraded


def _convert_flat_config(flat: dict) -> dict:
    """Convert flat config format to nested format for backwards compatibility.

    Args:
        flat: Raw dictionary with top-level fields (e.g., 'resolution').

    Returns:
        A nested dictionary structure aligned with v2 schemas.
    """
    nested: dict = {
        "dataset": {},
        "camera": {},
        "tag": {},
        "scene": {},
        "physics": {},
        "scenario": {},
    }

    key_map = {
        "resolution": ("camera", "resolution"),
        "samples": ("camera", "samples_per_scene"),
        "tag_family": ("tag", "family"),
        "lighting": ("scene", "lighting"),
        "physics": ("physics", None),  # None means copy whole dict
        "output_dir": ("dataset", "output_dir"),
        "intent": ("dataset", "intent"),
        "num_scenes": ("dataset", "num_scenes"),
        "seed": ("dataset", "seed"),
    }

    for flat_key, (section, nested_key) in key_map.items():
        if flat_key in flat:
            if section not in nested:
                nested[section] = {}

            if nested_key:
                nested[section][nested_key] = flat[flat_key]
            else:
                nested[section] = flat[flat_key]

    # Handle backgrounds
    if "backgrounds" in flat:
        bg = flat["backgrounds"]
        if "hdri_path" in bg:
            nested["scene"]["background_hdri"] = bg["hdri_path"]
        if "texture_dir" in bg:
            nested["scene"]["texture_dir"] = bg["texture_dir"]

    return nested


def _map_legacy_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Applies field-level legacy mappings to a nested configuration.

    Args:
        data: Nested configuration dictionary.

    Returns:
        The dictionary with legacy fields (e.g., 'intent', 'seed') mapped to modern equivalents.
    """

    # Map 'intent' -> 'evaluation_scopes' (DatasetConfig level)
    dataset = data.get("dataset", {})
    if isinstance(dataset, dict):
        if "intent" in dataset and "evaluation_scopes" not in dataset:
            intent_val = dataset["intent"]
            if intent_val == "calibration":
                dataset["evaluation_scopes"] = ["CALIBRATION"]
            elif "pose" in str(intent_val):
                dataset["evaluation_scopes"] = [
                    "DETECTION",
                    "POSE_ACCURACY",
                    "CORNER_PRECISION",
                ]

        # Map legacy top-level 'seed' in dataset section
        if "seed" in dataset:
            if "seeds" not in dataset:
                dataset["seeds"] = {}
            if isinstance(dataset["seeds"], dict) and "global_seed" not in dataset["seeds"]:
                dataset["seeds"]["global_seed"] = dataset.pop("seed")

        data["dataset"] = dataset

    # Map legacy sensor dynamics (CameraConfig level)
    camera = data.get("camera", {})
    if isinstance(camera, dict):
        dynamics = camera.get("sensor_dynamics", {})
        if isinstance(dynamics, dict):
            legacy_fields = ["velocity_mean", "velocity_std", "shutter_time_ms"]
            for field in legacy_fields:
                if field in camera and field not in dynamics:
                    dynamics[field] = camera.pop(field)

            if "shutter_speed" in camera:
                dynamics["shutter_time_ms"] = camera.pop("shutter_speed") * 1000.0

            if "rolling_shutter_readout" in camera:
                dynamics["rolling_shutter_duration_ms"] = camera.pop("rolling_shutter_readout")

            if dynamics:
                camera["sensor_dynamics"] = dynamics
        data["camera"] = camera

    # Map legacy layout -> polymorphic subject (ScenarioConfig level)
    scenario = data.get("scenario", {})
    if isinstance(scenario, dict) and "subject" not in scenario:
        if "tag_families" in scenario or "tags_per_scene" in scenario:
            scenario["subject"] = {
                "type": "TAGS",
                "tag_families": scenario.pop("tag_families", ["tag36h11"]),
                "size_meters": scenario.pop("tag_size", 0.1),
                "tags_per_scene": scenario.pop("tags_per_scene", 10),
            }
        elif ("layout" in scenario and scenario["layout"] == "board") or "board" in scenario:
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
        data["scenario"] = scenario

    return data
