import json
import subprocess
from unittest.mock import MagicMock

import pytest

from render_tag.backend.engine import RenderContext, execute_recipe
from render_tag.cli.tools import check_blenderproc_installed

# Skip if blenderproc not available
pytestmark = pytest.mark.skipif(
    not check_blenderproc_installed(), reason="BlenderProc is not installed"
)


def test_rolling_shutter_integration_cli_flags(tmp_path):
    """Verify that CLI handles rolling shutter flags correctly."""
    output_dir = tmp_path
    config_path = output_dir / "shutter_config.yaml"
    # Resolution must be large enough that sampled tags meet the validator's
    # visibility criteria (area >= 36 px for tag36h11). At 64x64 every camera
    # sample fails visibility, and SceneCompiler.compile_scene(validate=True)
    # exhausts its retry budget.
    config_path.write_text("""
dataset:
  seed: 42
  num_scenes: 1
camera:
  resolution: [320, 240]
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


def test_rolling_shutter_backend_mapping_no_errors(tmp_path, stabilized_bridge):
    """
    Staff Engineer: Verify that backend handles rolling shutter data without crashing.
    Using direct execute_recipe call with mocks for speed and reliability.
    """
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    from render_tag.core.schema.recipe import SceneRecipe

    recipe = SceneRecipe(
        scene_id=1,
        random_seed=42,
        renderer={"mode": "workbench"},
        cameras=[
            {
                "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                "intrinsics": {
                    "resolution": [32, 32],
                    "k_matrix": [[1, 0, 16], [0, 1, 16], [0, 0, 1]],
                    "fov": 60.0,
                },
                "sensor_dynamics": {"rolling_shutter_duration_ms": 5.0, "shutter_time_ms": 10.0},
            }
        ],
        objects=[],
        world={},
    )

    ctx = RenderContext(
        output_dir=output_dir,
        renderer_mode="workbench",
        csv_writer=MagicMock(),
        coco_writer=MagicMock(),
        rich_writer=MagicMock(),
        provenance_writer=MagicMock(),
        global_seed=42,
        skip_visibility=True,
    )

    # This verifies that engine.py -> camera.py -> blender mapping works without crash
    execute_recipe(recipe, ctx)

    # If we reached here, no crash occurred
    assert (output_dir / "images" / "scene_0001_cam_0000.png").exists()
