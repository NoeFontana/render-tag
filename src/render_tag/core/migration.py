"""
Schema Migration Engine for render-tag.

Handles upgrading legacy configuration dictionaries to the current standard
before Pydantic validation.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from render_tag.core.constants import CURRENT_SCHEMA_VERSION
from render_tag.core.logging import get_logger

logger = get_logger(__name__)


class SchemaMigrator:
    """
    Orchestrates sequential migration of schema dictionaries.
    """

    def __init__(self, target_version: str = CURRENT_SCHEMA_VERSION):
        self.target_version = target_version
        # Map of (from_version) -> transformation_function
        self._registry: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "0.0": self._migrate_0_0_to_0_1,
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
