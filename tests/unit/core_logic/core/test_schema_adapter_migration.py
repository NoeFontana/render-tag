"""Tests for the Anti-Corruption Layer (schema_adapter)."""

from __future__ import annotations

import pytest

from render_tag.core.schema_adapter import SchemaMigrator, adapt_config


class TestMigrate01To02:
    """Regression tests for v0.1 -> v0.2 migration (polymorphic subject)."""

    def test_tag_size_meters_preserved_without_scenario_fields(self):
        """tag.size_meters must be honored even when scenario has no tag_families/tags_per_scene.

        Regression: previously the ACL only consulted tag.size_meters inside the
        `if "tag_families" in scenario or "tags_per_scene" in scenario` branch, so a
        config with only `tag: {size_meters: 0.16}` silently defaulted to 0.1 m via
        Pydantic's default_factory.
        """
        data = {"version": "0.1", "tag": {"size_meters": 0.16}}

        with pytest.warns(DeprecationWarning):
            upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        subject = upgraded["scenario"]["subject"]
        assert subject["type"] == "TAGS"
        assert subject["size_mm"] == 160.0

    def test_tag_family_preserved_without_scenario_fields(self):
        """tag.family must be honored when scenario has no tag_families."""
        data = {"version": "0.1", "tag": {"family": "tag16h5", "size_meters": 0.05}}

        with pytest.warns(DeprecationWarning):
            upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        subject = upgraded["scenario"]["subject"]
        assert subject["tag_families"] == ["tag16h5"]
        assert subject["size_mm"] == 50.0

    def test_end_to_end_adapt_config_surfaces_size_mm(self):
        """Full adapt_config pipeline must surface the legacy tag size as size_mm."""
        data = {"version": "0.1", "tag": {"size_meters": 0.16}}

        with pytest.warns(DeprecationWarning):
            adapted = adapt_config(data)

        assert adapted["scenario"]["subject"]["size_mm"] == 160.0

    def test_scenario_tag_size_overrides_tag_section(self):
        """scenario.tag_size takes precedence over tag.size_meters when both are set."""
        data = {
            "version": "0.1",
            "tag": {"size_meters": 0.1},
            "scenario": {"tag_size": 0.2, "tag_families": ["tag36h11"]},
        }

        with pytest.warns(DeprecationWarning):
            upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        assert upgraded["scenario"]["subject"]["size_mm"] == 200.0

    def test_board_layout_left_alone(self):
        """Legacy Board configs are not coerced into TAGS subjects."""
        data = {"version": "0.1", "scenario": {"layout": "board"}}

        upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        assert "subject" not in upgraded["scenario"]

    def test_tags_per_scene_tuple_collapsed_to_max(self):
        """Legacy [min, max] tuple collapses to max (existing behavior preserved)."""
        data = {"version": "0.1", "scenario": {"tags_per_scene": [1, 5]}}

        with pytest.warns(DeprecationWarning):
            upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        assert upgraded["scenario"]["subject"]["tags_per_scene"] == 5

    def test_noop_when_no_legacy_fields(self):
        """Pure v0.1 config with no legacy tag/scenario fields passes through unchanged."""
        data = {"version": "0.1", "dataset": {"num_scenes": 10}}

        upgraded = SchemaMigrator()._migrate_0_1_to_0_2(data)

        assert upgraded["version"] == "0.2"
        assert "subject" not in upgraded.get("scenario", {})


@pytest.mark.parametrize(
    "size_meters_in,expected_size_mm",
    [(0.16, 160.0), (0.05, 50.0), (0.1, 100.0)],
)
def test_size_meters_round_trip_to_size_mm(size_meters_in, expected_size_mm):
    """Legacy tag.size_meters should end up as size_mm after full model validation."""
    from render_tag.core.config import GenConfig

    data = {"version": "0.1", "tag": {"size_meters": size_meters_in}}
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(data)
    config = GenConfig.model_validate(adapted)

    subject = config.scenario.subject
    assert subject is not None
    assert subject.root.size_mm == expected_size_mm  # type: ignore[union-attr]
