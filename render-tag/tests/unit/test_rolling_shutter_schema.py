import pytest
from pydantic import ValidationError

from render_tag.core.config import CameraConfig, GenConfig


def test_camera_config_rolling_shutter_valid():
    """Verify that valid rolling shutter duration is accepted."""
    # Test within a SensorDynamics-like structure (if refactored) or directly if not yet.
    # The spec says "within a new sensor_dynamics grouping".
    # Let's assume we implement it under CameraConfig.sensor_dynamics.

    # We will first test direct attribute if grouping isn't there yet,
    # but the task says "Refactor CameraConfig... to group sensor dynamics".
    # So the test should expect the grouping.

    config_dict = {
        "sensor_dynamics": {"rolling_shutter_duration_ms": 10.0, "shutter_time_ms": 20.0}
    }
    cam = CameraConfig(**config_dict)
    assert cam.sensor_dynamics.rolling_shutter_duration_ms == 10.0


def test_camera_config_rolling_shutter_invalid():
    """Verify that negative rolling shutter duration is rejected."""
    with pytest.raises(ValidationError):
        CameraConfig(sensor_dynamics={"rolling_shutter_duration_ms": -1.0})


def test_gen_config_serialization_with_rolling_shutter():
    """Verify that GenConfig correctly includes rolling shutter in model_dump."""
    config = GenConfig()
    # default should be 0.0 or grouping should exist
    assert hasattr(config.camera, "sensor_dynamics")
    config.camera.sensor_dynamics.rolling_shutter_duration_ms = 5.0

    dump = config.model_dump()
    assert dump["camera"]["sensor_dynamics"]["rolling_shutter_duration_ms"] == 5.0
