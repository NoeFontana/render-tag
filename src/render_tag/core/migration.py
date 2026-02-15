"""
Schema Migration Engine for render-tag.

Handles upgrading legacy configuration dictionaries to the current standard
before Pydantic validation.
"""

from typing import Any, Callable

from render_tag.core.logging import get_logger

logger = get_logger(__name__)


class SchemaMigrator:
    """
    Orchestrates sequential migration of schema dictionaries.
    """

    def __init__(self, target_version: str = "1.0"):
        self.target_version = target_version
        # Map of (from_version) -> transformation_function
        self._registry: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "0.0": self._migrate_0_0_to_1_0,
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

            logger.info(f"Migrating schema: {current_version} -> 1.0")
            current_data = transform(current_data)
            current_version = self.get_version(current_data)

        return current_data

    def _migrate_0_0_to_1_0(self, data: dict[str, Any]) -> dict[str, Any]:
        """Base migration: Adds the mandatory version field."""
        upgraded = data.copy()
        upgraded["version"] = "1.0"
        return upgraded
