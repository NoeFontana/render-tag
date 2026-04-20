import pytest

from render_tag.core.constants import CURRENT_SCHEMA_VERSION
from render_tag.core.schema import migrations
from render_tag.core.schema_adapter import SchemaMigrator


def test_migrator_detects_legacy_version():
    """Verify that missing version defaults to 0.0."""
    migrator = SchemaMigrator()
    data = {"foo": "bar"}
    assert migrator.get_version(data) == "0.0"


def test_migrator_detects_explicit_version():
    """Verify that explicit version field is respected."""
    migrator = SchemaMigrator()
    data = {"version": "0.1", "foo": "bar"}
    assert migrator.get_version(data) == "0.1"


def test_migrator_upgrades_0_0_to_1_0():
    """Verify sequential migration from 0.0 to 0.1."""
    migrator = SchemaMigrator(target_version="0.1")
    data = {"foo": "bar"}

    migrated_data = migrator.migrate(data)

    assert migrated_data["version"] == "0.1"
    assert migrated_data["foo"] == "bar"


def test_migrator_raises_on_unsupported_version():
    """Verify error when version is newer than supported."""
    migrator = SchemaMigrator(target_version="0.1")
    data = {"version": "99.9"}

    with pytest.raises(ValueError, match="Unsupported version"):
        migrator.migrate(data)


def test_registry_is_complete():
    """The migration chain must reach CURRENT_SCHEMA_VERSION from '0.0' with no gaps.

    `migrations.__init__` performs this check at import time and raises
    ImportError if it fails. This test is a surface check that asserts
    the starting version is registered and the end state is reachable —
    protecting the invariant that adding a new version requires adding a
    migration module with the right FROM/TO, not just bumping a constant.
    """
    assert "0.0" in migrations.REGISTRY

    visited: list[str] = []
    version = "0.0"
    for _ in range(20):  # guard against cycles even though import-time check does too
        visited.append(version)
        if version == CURRENT_SCHEMA_VERSION:
            break
        transform = migrations.REGISTRY[version]
        next_version = transform({}).get("version")
        assert isinstance(next_version, str) and next_version != version
        version = next_version
    else:
        pytest.fail(f"Chain did not terminate within 20 hops; visited={visited}")

    assert visited[-1] == CURRENT_SCHEMA_VERSION
