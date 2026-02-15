import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from render_tag.cli.tools import check_blenderproc_installed

# Skip if blenderproc not available
pytestmark = pytest.mark.skipif(
    not check_blenderproc_installed(), reason="BlenderProc is not installed"
)


def test_rolling_shutter_integration_cli_flags():
    """Verify that CLI handles rolling shutter flags correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        config_path = output_dir / "shutter_config.yaml"
        config_path.write_text("""
dataset:
  seed: 42
  num_scenes: 1
camera:
  resolution: [64, 64]
  sensor_dynamics:
    rolling_shutter_duration_ms: 10.0
    shutter_time_ms: 20.0
""")

        # Run with --skip-render to verify recipe generation
        result = subprocess.run(
            [
                "render-tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(output_dir),
                "--skip-render",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Check generated recipe
        recipe_path = output_dir / "recipes_shard_0.json"
        assert recipe_path.exists()

        with open(recipe_path) as f:
            recipes = json.load(f)
            dynamics = recipes[0]["cameras"][0]["sensor_dynamics"]
            assert dynamics["rolling_shutter_duration_ms"] == 10.0
            assert dynamics["shutter_time_ms"] == 20.0


@pytest.mark.integration
def test_rolling_shutter_backend_mapping_no_errors():
    """Verify that actual rendering with rolling shutter enabled doesn't crash."""
    # Use mock executor if we want fast test, or full cycles if we want validation.
    # Actually, we want to verify that the backend doesn't crash when it receives the data.

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        config_path = output_dir / "render_config.yaml"
        # We use workbench here to test the warning logic and ensure it doesn't crash
        config_path.write_text("""
dataset:
  num_scenes: 1
camera:
  resolution: [32, 32]
  samples_per_scene: 1
  sensor_dynamics:
    rolling_shutter_duration_ms: 5.0
""")

        import sys

        # Run actual rendering with workbench (should issue warning but succeed)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "render_tag",
                "generate",
                "--config",
                str(config_path),
                "--output",
                str(output_dir),
                "--renderer-mode",
                "workbench",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0
        # Command success is enough to verify no crash occurred in backend
