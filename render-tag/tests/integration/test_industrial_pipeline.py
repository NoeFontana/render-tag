import subprocess
import pytest
import yaml
from pathlib import Path

@pytest.fixture
def industrial_config(tmp_path):
    config = {
        "dataset": {
            "output_dir": str(tmp_path / "output"),
            "num_scenes": 1
        },
        "camera": {
            "resolution": [512, 512],
            "sensor_noise": {
                "model": "salt_and_pepper",
                "amount": 0.05,
                "salt_vs_pepper": 0.5
            },
            # Add motion blur params if desired
            "velocity_mean": 1.0,
            "shutter_time_ms": 10.0
        },
        "scene": {
            "lighting_preset": "factory"
        },
        "tag": {
            "family": "tag36h11",
            "material": {
                "randomize": True,
                "roughness_min": 0.5,
                "roughness_max": 0.9
            }
        }
    }
    config_path = tmp_path / "industrial_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path

def test_industrial_pipeline(tmp_path, industrial_config):
    """Test full pipeline with industrial features enabled."""
    result = subprocess.run(
        [
            "render-tag",
            "generate",
            "--config",
            str(industrial_config),
            "--output",
            str(tmp_path / "output"),
            "--scenes",
            "1"
        ],
        capture_output=True,
        text=True,
        timeout=300
    )
    assert result.returncode == 0, f"Failed: {result.stderr}"
    
    # Check output
    output_dir = tmp_path / "output"
    assert (output_dir / "images/scene_0000_cam_0000.png").exists()
    assert (output_dir / "tags.csv").exists()
    
    # Check if we can load the CSV and find detections
    # (Just existence check is enough for pipeline integrity)
    assert (output_dir / "annotations.json").exists()
