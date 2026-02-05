import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from render_tag.cli import app
from pathlib import Path

runner = CliRunner()

@patch("render_tag.cli.AssetValidator")
def test_cli_catches_validation_error(mock_validator, tmp_path):
    mock_validator.return_value.is_hydrated.return_value = True
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text("dataset:\n  num_scenes: -5\n")
    result = runner.invoke(app, ["generate", "--config", str(config_path)])
    assert result.exit_code == 1
    assert "Validation Error" in result.stdout
    assert "Input should be greater than 0" in result.stdout

@patch("render_tag.cli.AssetValidator")
def test_cli_detects_missing_asset_preflight(mock_validator, tmp_path):
    mock_validator.return_value.is_hydrated.return_value = False
    config_path = tmp_path / "missing_asset.yaml"
    config_path.write_text("scene:\n  background_hdri: nonexistent_studio.exr\n")
    result = runner.invoke(app, ["generate", "--config", str(config_path), "--skip-render"])
    assert result.exit_code == 1
    assert "Required assets missing" in result.stdout
    assert "assets pull" in result.stdout
