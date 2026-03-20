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
        "scenario": {}
    }
    adapted = adapt_config(config)
    assert adapted["version"] == "0.2"
    assert adapted["dataset"]["name"] == "test"

def test_adapt_config_legacy_intent():
    """Verify legacy 'intent' mapping."""
    # Test flat intent
    config = {"intent": "calibration"}
    adapted = adapt_config(config)
    assert "evaluation_scopes" in adapted["dataset"]
    assert "CALIBRATION" in adapted["dataset"]["evaluation_scopes"]

def test_adapt_config_nested_legacy_intent():
    """Verify nested legacy 'intent' mapping."""
    config = {"dataset": {"intent": "pose_estimation"}}
    adapted = adapt_config(config)
    assert "DETECTION" in adapted["dataset"]["evaluation_scopes"]
    assert "POSE_ACCURACY" in adapted["dataset"]["evaluation_scopes"]

def test_adapt_config_legacy_seed():
    """Verify legacy 'seed' mapping."""
    # Test flat seed
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
    config = {"resolution": [1280, 720]}
    adapted = adapt_config(config)
    assert adapted["camera"]["resolution"] == [1280, 720]

def test_adapt_config_legacy_sensor_dynamics():
    """Verify legacy sensor dynamics mapping."""
    config = {
        "camera": {
            "velocity_mean": 1.0,
            "shutter_speed": 0.01  # 0.01s -> 10ms
        }
    }
    adapted = adapt_config(config)
    dynamics = adapted["camera"]["sensor_dynamics"]
    assert dynamics["velocity_mean"] == 1.0
    assert dynamics["shutter_time_ms"] == 10.0

def test_adapt_config_legacy_tag_layout():
    """Verify legacy TAGS layout migration."""
    config = {
        "scenario": {
            "tag_families": ["tag16h5"],
            "tag_size": 0.16
        }
    }
    adapted = adapt_config(config)
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "TAGS"
    assert subject["tag_families"] == ["tag16h5"]
    assert subject["size_meters"] == 0.16

def test_adapt_config_legacy_board_layout():
    """Verify legacy BOARD layout migration."""
    config = {
        "scenario": {
            "layout": "board",
            "grid_size": [5, 4],
            "marker_size": 0.05
        }
    }
    adapted = adapt_config(config)
    subject = adapted["scenario"]["subject"]
    assert subject["type"] == "BOARD"
    assert subject["rows"] == 4
    assert subject["cols"] == 5
    assert subject["marker_size"] == 0.05
