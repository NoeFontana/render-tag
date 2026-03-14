from pathlib import Path
from unittest.mock import patch

import pytest

from render_tag.data_io.assets import AssetProvider


@pytest.fixture
def temp_assets_dir(tmp_path):
    d = tmp_path / "assets"
    d.mkdir()
    (d / "tags").mkdir()
    return d


def test_asset_provider_resolves_local_existing(temp_assets_dir):
    # Create a dummy local asset
    tag_path = temp_assets_dir / "tags" / "test_tag.png"
    tag_path.write_text("dummy content")

    provider = AssetProvider(local_dir=temp_assets_dir)
    resolved = provider.resolve_path("tags/test_tag.png")

    assert resolved == tag_path
    assert resolved.exists()


@patch("render_tag.data_io.assets.hf_hub_download")
def test_asset_provider_downloads_if_missing(mock_hf_download, temp_assets_dir):
    # Target path does not exist locally
    target_rel_path = "tags/missing_tag.png"
    expected_path = temp_assets_dir / target_rel_path

    # Mock hf_hub_download to simulate downloading the file
    def side_effect(repo_id, filename, local_dir, repo_type, **kwargs):
        p = Path(local_dir) / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("downloaded content")
        return str(p)

    mock_hf_download.side_effect = side_effect

    provider = AssetProvider(local_dir=temp_assets_dir, repo_id="test/repo")
    resolved = provider.resolve_path(target_rel_path)

    assert resolved == expected_path
    assert resolved.exists()
    assert resolved.read_text() == "downloaded content"

    mock_hf_download.assert_called_once_with(
        repo_id="test/repo",
        filename=target_rel_path,
        local_dir=str(temp_assets_dir),
        repo_type="dataset",
    )


def test_asset_provider_absolute_path_passthrough(temp_assets_dir):
    # If an absolute path is provided that exists, it should be returned as is
    abs_path = temp_assets_dir / "absolute_test.png"
    abs_path.write_text("abs content")

    provider = AssetProvider(local_dir=temp_assets_dir)
    resolved = provider.resolve_path(str(abs_path))

    assert resolved == abs_path


@patch("render_tag.data_io.assets.hf_hub_download")
def test_asset_provider_download_failure_raises_asset_error(mock_hf_download, temp_assets_dir):
    """Download failure must raise AssetError instead of silently returning a bad path."""
    from render_tag.core.errors import AssetError

    mock_hf_download.side_effect = Exception("HF Error")

    provider = AssetProvider(local_dir=temp_assets_dir)
    target_rel_path = "tags/error_tag.png"

    with pytest.raises(AssetError, match="Failed to download asset"):
        provider.resolve_path(target_rel_path)
