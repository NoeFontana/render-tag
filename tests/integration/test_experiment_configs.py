import subprocess
from pathlib import Path

import pytest


def get_experiment_configs():
    """Discover all experiment configs in the repository."""
    # Find repo root (assuming running from root or tests/)
    root = Path(__file__).resolve().parents[2]
    config_dir = root / "configs" / "experiments"
    if not config_dir.exists():
        return []
    return list(config_dir.glob("*.yaml"))


@pytest.mark.integration
@pytest.mark.parametrize("config_path", get_experiment_configs())
def test_experiment_config_validity(config_path):
    """
    Test that each experiment config in configs/experiments produces valid
    scene recipes (Shadow Render mode).
    """
    # Use 'uv run render-tag' to ensure we use the development environment
    result = subprocess.run(
        [
            "render-tag",
            "experiment",
            "run",
            "--config",
            str(config_path),
            "--skip-render",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(f"Experiment config {config_path.name} failed validation:\n{result.stderr}")

    assert "Completed Successfully" in result.stdout


def test_visibility_validation_failure(tmp_path):
    """
    Verify that the visibility validator actually catches frames with no visible tags.
    """
    # 1. Create a config that looks away from the origin (where tags are placed)
    broken_config_path = tmp_path / "broken_viz.yaml"
    broken_config_path.write_text(
        """
dataset:
  num_scenes: 1
  seeds:
    layout_seed: 42
    camera_seed: 42

camera:
  resolution: [640, 480]
  fov: 60.0
  samples_per_scene: 1
  # Very far away and looking away
  min_distance: 100.0 
  max_distance: 105.0
  min_elevation: 0.8
  max_elevation: 0.9
  azimuth: 180.0 # Looking opposite of center

tag:
  family: tag36h11
  size_meters: 0.1

scenario:
  layout: plain
  tags_per_scene: [1, 1]
"""
    )

    # 2. Run generate with skip-render (it uses the same validator)
    result = subprocess.run(
        [
            "render-tag",
            "generate",
            "--config",
            str(broken_config_path),
            "--output",
            str(tmp_path / "output"),
            "--skip-render",
        ],
        capture_output=True,
        text=True,
    )

    # It should produce a warning about no tags visible
    # Normalize whitespace to handle console wrapping
    combined = " ".join((result.stdout + result.stderr).split())
    assert "No tags meet visibility criteria" in combined
    assert "fully in view" in combined
    assert "angle <= 80" in combined
