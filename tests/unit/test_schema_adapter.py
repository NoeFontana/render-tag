import warnings

import pytest

from render_tag.core.schema_adapter import adapt_config


def test_adapt_config_identity():
    """Verify that a modern config is returned unchanged (mostly)."""
    config = {
        "version": "0.2",
        "dataset": {"name": "test"},
        "camera": {},
        "tag": {},
        "scene": {},
        "physics": {},
        "scenario": {},
    }
    adapted = adapt_config(config)
    assert adapted["version"] == "0.2"
    assert adapted["dataset"]["name"] == "test"


def test_adapt_config_legacy_intent():
    """Verify legacy 'intent' mapping."""
    config = {"intent": "calibration"}
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)
    assert "evaluation_scopes" in adapted["dataset"]
    assert "CALIBRATION" in adapted["dataset"]["evaluation_scopes"]


def test_adapt_config_nested_legacy_intent():
    """Verify nested legacy 'intent' mapping."""
    config = {"dataset": {"intent": "pose_estimation"}}
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)
    assert "DETECTION" in adapted["dataset"]["evaluation_scopes"]
    assert "POSE_ACCURACY" in adapted["dataset"]["evaluation_scopes"]


def test_adapt_config_legacy_seed():
    """Verify legacy 'seed' mapping."""
    config = {"seed": 1234}
    adapted = adapt_config(config)
    assert adapted["dataset"]["seeds"]["global_seed"] == 1234


def test_adapt_config_nested_legacy_seed():
    """Verify nested legacy 'seed' mapping."""
    config = {"dataset": {"seed": 5678}}
    adapted = adapt_config(config)
    assert adapted["dataset"]["seeds"]["global_seed"] == 5678


def test_adapt_config_flat_layout():
    """Verify flat config conversion."""
    config = {
        "resolution": [1280, 720],
        "samples": 32,
        "tag_family": "tag36h11",
        "lighting": "factory",
        "output_dir": "test_output",
        "intent": "calibration",
        "seed": 999,
    }
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)
    assert adapted["camera"]["resolution"] == [1280, 720]
    assert adapted["camera"]["samples_per_scene"] == 32
    assert adapted["scenario"]["subject"]["tag_families"] == ["tag36h11"]
    assert adapted["scene"]["lighting"] == "factory"
    assert adapted["dataset"]["output_dir"] == "test_output"
    assert "CALIBRATION" in adapted["dataset"]["evaluation_scopes"]
    assert adapted["dataset"]["seeds"]["global_seed"] == 999


def test_adapt_config_legacy_sensor_dynamics():
    """Verify legacy sensor dynamics mapping."""
    config = {
        "camera": {
            "velocity_mean": 1.0,
            "shutter_speed": 0.01,  # 0.01s -> 10ms
        }
    }
    adapted = adapt_config(config)
    dynamics = adapted["camera"]["sensor_dynamics"]
    assert dynamics["velocity_mean"] == 1.0
    assert dynamics["shutter_time_ms"] == 10.0


def test_adapt_config_legacy_tag_layout():
    """Verify legacy TAGS layout migration."""
    config = {"scenario": {"tag_families": ["tag16h5"], "tag_size": 0.16}}
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "TAGS"
    assert subject["tag_families"] == ["tag16h5"]
    assert subject["size_mm"] == 160.0


def test_adapt_config_legacy_board_layout():
    """Verify legacy BOARD layout migration."""
    config = {"scenario": {"layout": "board", "grid_size": [5, 4], "marker_size": 0.05}}
    with pytest.warns(DeprecationWarning, match="scenario.layout"):
        adapted = adapt_config(config)
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "BOARD"
    assert subject["rows"] == 4
    assert subject["cols"] == 5
    assert subject["marker_size"] == 0.05
    assert "layout" not in adapted["scenario"]


# --- Characterization tests (pre-refactor baseline) -----------------------------
#
# These tests pin down current behavior on cases that were previously untested.
# They must pass on main and stay unchanged through the schema_adapter split
# (plan-4-split-expressive-reddy.md). Their purpose is to catch ordering or
# equivalence regressions introduced by the refactor.


def test_flat_v0_0_end_to_end():
    """Flat v0.0 config with pose intent round-trips all three ACL passes.

    Exercises flat-to-nested + migrator + field-map together: the flat shim
    turns top-level keys into sections, the migrator synthesizes
    scenario.subject from tag.family, and the field map rewrites intent/seed
    and strips the (now-dead) tag section.
    """
    config = {
        "resolution": [640, 480],
        "samples": 16,
        "tag_family": "tag16h5",
        "intent": "pose_estimation",
        "seed": 42,
    }
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)

    assert adapted["version"] == "0.2"
    assert adapted["camera"]["resolution"] == [640, 480]
    assert adapted["camera"]["samples_per_scene"] == 16
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "TAGS"
    assert subject["tag_families"] == ["tag16h5"]
    assert "family" not in adapted.get("tag", {})
    assert adapted["dataset"]["evaluation_scopes"] == [
        "DETECTION",
        "POSE_ACCURACY",
        "CORNER_PRECISION",
    ]
    assert adapted["dataset"]["seeds"]["global_seed"] == 42


def test_multi_hop_v0_0_to_v0_2():
    """A dict without a version field traverses both migration hops."""
    config = {
        "dataset": {"num_scenes": 3},
        "scenario": {"tag_families": ["tag36h11"], "tags_per_scene": 4, "tag_size": 0.1},
    }
    with pytest.warns(DeprecationWarning):
        adapted = adapt_config(config)

    assert adapted["version"] == "0.2"
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "TAGS"
    assert subject["tag_families"] == ["tag36h11"]
    assert subject["tags_per_scene"] == 4
    assert subject["size_mm"] == 100.0


@pytest.mark.parametrize(
    "scenario_in,expected_subject",
    [
        (
            {"tag_families": ["tag36h11"], "tag_size": 0.08},
            {
                "type": "TAGS",
                "tag_families": ["tag36h11"],
                "size_mm": 80.0,
                "tags_per_scene": 10,
            },
        ),
        (
            {"tag_families": ["tag16h5"], "tags_per_scene": 2, "tag_size": 0.05},
            {
                "type": "TAGS",
                "tag_families": ["tag16h5"],
                "size_mm": 50.0,
                "tags_per_scene": 2,
            },
        ),
    ],
)
def test_v01_tag_scenario_fields_synthesize_subject(scenario_in, expected_subject):
    """Legacy v0.1 scenario.tag_families/tag_size/tags_per_scene → subject.

    Originally characterization test ``test_subject_synthesis_paths_equivalent``
    pinned down that the migrator and field-map produced identical subjects
    for these inputs. Having confirmed equivalence on main, PR 3 dropped the
    field-map duplicate. This test now protects the migrator's end-to-end
    behavior for the cases that used to be dual-covered.
    """
    config = {"version": "0.1", "scenario": dict(scenario_in)}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        adapted = adapt_config(config)

    assert adapted["scenario"]["subject"] == expected_subject


def test_order_dependence_migrator_before_flat_breaks():
    """Running the migrator before flat-to-nested produces wrong output.

    The migrator assumes nested structure (reads scenario.* and tag.*). Given
    a flat config, it sees no scenario section and synthesizes nothing,
    producing a config that still has top-level flat keys. This test protects
    the ordering invariant during refactoring: if the refactor ever reorders
    the passes, the characterization fails.
    """
    from render_tag.core.schema_adapter import SchemaMigrator, _convert_flat_config

    flat = {
        "resolution": [1920, 1080],
        "tag_family": "tag36h11",
        "intent": "calibration",
    }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        wrong_order = SchemaMigrator().migrate(dict(flat))
    assert "camera" not in wrong_order
    assert wrong_order.get("resolution") == [1920, 1080]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        right_order = _convert_flat_config(dict(flat))
        right_order = SchemaMigrator().migrate(right_order)
    assert right_order["camera"]["resolution"] == [1920, 1080]


def test_order_dependence_field_map_before_migrator_breaks():
    """Field map before migrator misses the scenario.subject synthesis path.

    The field map only synthesizes scenario.subject when subject is absent and
    scenario has tag_families/tags_per_scene. A v0.1 config with only
    tag.size_meters would be stripped by the field map (tag section cleared)
    before the migrator could consume it, producing a config with no subject
    at all. This test protects the ordering invariant.
    """
    from render_tag.core.schema_adapter import SchemaMigrator, _map_legacy_fields

    config = {"version": "0.1", "tag": {"size_meters": 0.16}}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        after_field_map_first = _map_legacy_fields(dict(config, tag=dict(config["tag"])))
        after_field_map_first = SchemaMigrator().migrate(after_field_map_first)

    assert "subject" not in after_field_map_first.get("scenario", {})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        right_order = SchemaMigrator().migrate(dict(config, tag=dict(config["tag"])))
        right_order = _map_legacy_fields(right_order)

    assert right_order["scenario"]["subject"]["size_mm"] == 160.0
