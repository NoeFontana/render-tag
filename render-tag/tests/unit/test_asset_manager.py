import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from render_tag.orchestration.assets import AssetManager

@pytest.fixture
def temp_assets_dir(tmp_path):
    """Create a temporary assets directory structure."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    return assets_dir

def test_asset_manager_init_creates_directories(temp_assets_dir):
    """Verify that AssetManager initializes the required subdirectories."""
    manager = AssetManager(local_dir=temp_assets_dir)
    
    # Expected subdirectories
    expected = ["hdri", "textures", "tags", "models"]
    for sub in expected:
        assert (temp_assets_dir / sub).exists()
        assert (temp_assets_dir / sub).is_dir()

@patch("render_tag.orchestration.assets.snapshot_download")
def test_asset_manager_pull(mock_download, temp_assets_dir):
    """Verify that pull calls snapshot_download with correct parameters."""
    manager = AssetManager(local_dir=temp_assets_dir, repo_id="test/repo")
    manager.pull(token="test_token")
    
    mock_download.assert_called_once()
    args, kwargs = mock_download.call_args
    assert kwargs["repo_id"] == "test/repo"
    assert kwargs["local_dir"] == str(temp_assets_dir)
    assert kwargs["token"] == "test_token"
    assert kwargs["repo_type"] == "dataset"

@patch("render_tag.orchestration.assets.upload_folder")
def test_asset_manager_push(mock_upload, temp_assets_dir):
    """Verify that push calls upload_folder with correct parameters."""
    manager = AssetManager(local_dir=temp_assets_dir, repo_id="test/repo")
    manager.push(token="test_token", commit_message="Update assets")
    
    mock_upload.assert_called_once()
    args, kwargs = mock_upload.call_args
    assert kwargs["repo_id"] == "test/repo"
    assert kwargs["folder_path"] == str(temp_assets_dir)
    assert kwargs["token"] == "test_token"
    assert kwargs["commit_message"] == "Update assets"
