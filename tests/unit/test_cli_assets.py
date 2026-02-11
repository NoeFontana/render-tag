"""
Unit tests for the assets CLI.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from render_tag.cli.main import app

runner = CliRunner()


@patch("render_tag.cli.assets.get_asset_manager")
def test_assets_pull_success(mock_get_manager):
    mock_manager = MagicMock()
    mock_get_manager.return_value = mock_manager
    
    result = runner.invoke(app, ["assets", "pull", "--token", "test_token"])
    
    assert result.exit_code == 0
    assert "Pulling assets" in result.stdout
    mock_manager.pull.assert_called_once_with(token="test_token")


@patch("render_tag.cli.assets.get_asset_manager")
def test_assets_pull_failure(mock_get_manager):
    mock_manager = MagicMock()
    mock_manager.pull.side_effect = Exception("Download failed")
    mock_get_manager.return_value = mock_manager
    
    result = runner.invoke(app, ["assets", "pull"])
    
    assert result.exit_code == 1
    assert "Error: Download failed" in result.stdout


@patch("render_tag.cli.assets.get_asset_manager")
def test_assets_push_success(mock_get_manager):
    mock_manager = MagicMock()
    mock_get_manager.return_value = mock_manager
    
    result = runner.invoke(app, ["assets", "push", "--token", "test_token", "--message", "feat: new textures"])
    
    assert result.exit_code == 0
    assert "Pushing assets" in result.stdout
    mock_manager.push.assert_called_once_with(token="test_token", commit_message="feat: new textures")


def test_assets_push_no_token():
    result = runner.invoke(app, ["assets", "push"])
    assert result.exit_code == 1
    assert "HF_TOKEN is required" in result.stdout
