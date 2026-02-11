from render_tag.common.validator import AssetValidator


def test_asset_validator_not_hydrated(tmp_path):
    """Verify that validator detects empty or missing assets folder."""
    # 1. Missing folder
    missing_dir = tmp_path / "nonexistent"
    validator = AssetValidator(missing_dir)
    assert validator.is_hydrated() is False

    # 2. Empty folder
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    validator = AssetValidator(empty_dir)
    assert validator.is_hydrated() is False

    # 3. Missing subdirs
    partial_dir = tmp_path / "partial"
    partial_dir.mkdir()
    (partial_dir / "hdri").mkdir()
    validator = AssetValidator(partial_dir)
    assert validator.is_hydrated() is False


def test_asset_validator_hydrated(tmp_path):
    """Verify that validator detects hydrated assets folder."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    for sub in ["hdri", "textures", "tags", "models"]:
        (assets_dir / sub).mkdir()

    # Add dummy file to one subdir
    (assets_dir / "hdri" / "test.exr").touch()

    validator = AssetValidator(assets_dir)
    assert validator.is_hydrated() is True
