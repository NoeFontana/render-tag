"""
Anti-Corruption Layer (ACL) for render-tag configuration.

This module handles the translation of legacy configuration formats into
the current v2-compliant internal schema before Pydantic validation.

The ACL runs four sequential passes in a non-commutative order:

1. ``flat_to_nested`` — rewrites pre-versioning flat dicts into nested shape.
2. ``migrations`` — versioned migration chain (v0.0 -> ... -> current).
3. ``field_map`` — declarative deprecated-field rewrites (sunset on schedule).
4. ``presets.expand`` — composes ``presets: [...]`` into overrides, with
   explicit user values winning over preset-supplied defaults.

See ``docs/engineering/schema_migrations.md`` for how to add new migrations
or legacy entries, and ``docs/guide.md`` (Presets) for the preset mechanism.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from render_tag.core import presets as _presets
from render_tag.core.constants import CURRENT_SCHEMA_VERSION
from render_tag.core.logging import get_logger
from render_tag.core.schema import migrations
from render_tag.core.schema.legacy import field_map, flat_to_nested

logger = get_logger(__name__)


def adapt_config(data: dict[str, Any]) -> dict[str, Any]:
    """Translate legacy config dicts into current-schema dicts.

    Primary entry point for the Anti-Corruption Layer. Runs the four passes
    in order; each pass assumes the output shape of the previous.
    """
    if data is None:
        return {}

    data = flat_to_nested.detect_and_convert(data)
    data = migrations.apply_chain(data)
    data = field_map.apply_all(data)
    data = _presets.expand(data)
    return data


class SchemaMigrator:
    """Thin wrapper over the migrations registry.

    Preserved as a public class for existing call sites (CLI, JobSpec) and
    tests that exercise ``_migrate_0_1_to_0_2`` directly. New code should
    prefer ``render_tag.core.schema.migrations.apply_chain``.
    """

    def __init__(self, target_version: str = CURRENT_SCHEMA_VERSION):
        self.target_version = target_version

    def get_version(self, data: dict[str, Any]) -> str:
        return migrations.get_version(data)

    def migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        return migrations.apply_chain(data, target_version=self.target_version)

    def upgrade_file_on_disk(self, path: Path | str, migrated_data: dict[str, Any]) -> None:
        """Overwrite an existing config file with its migrated form."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix not in {".yaml", ".yml", ".json"}:
            return
        if not path.exists():
            return
        logger.warning(f"Upgrading legacy file on disk: {path}")
        with open(path, "w") as f:
            if suffix == ".json":
                json.dump(migrated_data, f, indent=2)
            else:
                yaml.dump(migrated_data, f, sort_keys=False)

    def _migrate_0_0_to_0_1(self, data: dict[str, Any]) -> dict[str, Any]:
        from render_tag.core.schema.migrations import v0_0_to_v0_1

        return v0_0_to_v0_1.apply(data)

    def _migrate_0_1_to_0_2(self, data: dict[str, Any]) -> dict[str, Any]:
        from render_tag.core.schema.migrations import v0_1_to_v0_2

        return v0_1_to_v0_2.apply(data)


_convert_flat_config = flat_to_nested._convert
_map_legacy_fields = field_map.apply_all
