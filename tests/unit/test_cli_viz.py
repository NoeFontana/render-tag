"""
Unit tests for the visualization CLI.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


@patch("render_tag.cli.viz.visualize_recipe")
def test_viz_recipe_success(mock_viz, tmp_path: Path):
    recipe = tmp_path / "recipe.json"
    recipe.write_text("[]")
    
    result = runner.invoke(app, ["viz", "recipe", "--recipe", str(recipe), "--output", str(tmp_path / "viz")])
    
    assert result.exit_code == 0
    assert "Visualization saved to" in result.stdout
    mock_viz.assert_called_once()


@patch("render_tag.cli.viz.visualize_dataset")
def test_viz_dataset_success(mock_viz, tmp_path: Path):
    result = runner.invoke(app, ["viz", "dataset", "--output", str(tmp_path)])
    
    assert result.exit_code == 0
    mock_viz.assert_called_once()


@patch("render_tag.cli.viz.check_blenderproc_installed")
@patch("render_tag.cli.viz.subprocess.run")
def test_info_command(mock_run, mock_check):
    mock_check.return_value = True
    mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
    
    # info is still a shortcut or we can use viz info
    result = runner.invoke(app, ["info"])
    
    assert result.exit_code == 0
    assert "blenderproc is installed" in result.stdout
    assert "Supported Tag Families" in result.stdout
