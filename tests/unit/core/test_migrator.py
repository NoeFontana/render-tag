import pytest

from render_tag.core.migration import SchemaMigrator


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
