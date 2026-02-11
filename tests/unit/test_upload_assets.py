"""
Unit tests for asset upload utility.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock huggingface_hub before importing upload_assets
sys.modules["huggingface_hub"] = MagicMock()

from render_tag.tools.upload_assets import upload_assets


@patch("render_tag.tools.upload_assets.HfApi")
def test_upload_assets_dry_run(mock_hf_api, tmp_path: Path, capsys) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "test.txt").write_text("hello")

    upload_assets(assets_dir, "test/repo", dry_run=True)

    captured = capsys.readouterr()
    assert "[DRY RUN] Would upload" in captured.out
    assert "test.txt" in captured.out
    assert not mock_hf_api.return_value.upload_folder.called


@patch("render_tag.tools.upload_assets.HfApi")
def test_upload_assets_real(mock_hf_api, tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "test.txt").write_text("hello")

    upload_assets(assets_dir, "test/repo", token="secret")

    assert mock_hf_api.called
    assert mock_hf_api.return_value.upload_folder.called
    args, kwargs = mock_hf_api.return_value.upload_folder.call_args
    assert kwargs["repo_id"] == "test/repo"
    assert kwargs["folder_path"] == str(assets_dir)


def test_upload_assets_not_found(capsys) -> None:
    upload_assets(Path("/nonexistent"), "test/repo")
    captured = capsys.readouterr()
    assert "Error: Assets directory not found" in captured.out
