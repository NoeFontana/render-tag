import pytest
from unittest.mock import patch, MagicMock
import json
import yaml
from pathlib import Path
from typer.testing import CliRunner
from render_tag.cli import app

runner = CliRunner()

@pytest.fixture
def minimal_fast_config(tmp_path):
    config = {
        "dataset": {
            "num_scenes": 2
        },
        "scene": {
            "background_hdri": None,
            "texture_dir": None
        },
        "camera": {
            "samples_per_scene": 1
        }
    }
    config_path = tmp_path / "fast_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path

@patch("render_tag.cli.AssetValidator")
def test_generate_skip_render_creates_recipes(mock_validator, tmp_path, minimal_fast_config):
    """Verify that --skip-render generates recipe files but doesn't run Blender."""
    mock_validator.return_value.is_hydrated.return_value = True
    output_dir = tmp_path / "fast_output"
    
    # We pass --skip-render to avoid the slow Blender launch
    result = runner.invoke(app, [
        "generate",
        "--config", str(minimal_fast_config),
        "--output", str(output_dir),
        "--scenes", "2",
        "--skip-render"
    ])
    
    assert result.exit_code == 0, f"Command failed: {result.stdout}"
    assert "Skipping Blender launch" in result.stdout
    
    # Check that recipe files were created
    recipe_path = output_dir / "recipes_shard_0.json"
    assert recipe_path.exists()
    
    with open(recipe_path) as f:
        recipes = json.load(f)
        assert len(recipes) == 2
        assert recipes[0]["scene_id"] == 0
        assert recipes[1]["scene_id"] == 1

@patch("render_tag.cli.AssetValidator")
def test_generate_skip_render_respects_shards(mock_validator, tmp_path, minimal_fast_config):
    """Verify that --skip-render works correctly with sharding."""
    mock_validator.return_value.is_hydrated.return_value = True
    output_dir = tmp_path / "shard_output"
    
    # Run shard 1 of 2
    result = runner.invoke(app, [
        "generate",
        "--config", str(minimal_fast_config),
        "--output", str(output_dir),
        "--scenes", "4",
        "--total-shards", "2",
        "--shard-index", "1",
        "--skip-render"
    ])
    
    assert result.exit_code == 0, f"Command failed: {result.stdout}"
    
    # Recipe should be for shard 1 (Scenes 2 and 3)
    recipe_path = output_dir / "recipes_shard_1.json"
    assert recipe_path.exists()
    
    with open(recipe_path) as f:
        recipes = json.load(f)
        assert len(recipes) == 2
        assert recipes[0]["scene_id"] == 2
        assert recipes[1]["scene_id"] == 3