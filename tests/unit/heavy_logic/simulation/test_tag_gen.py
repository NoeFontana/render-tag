import cv2

from render_tag.generation.tags import ensure_tag_asset, generate_tag_image


def test_generate_apriltag():
    """Verify that an AprilTag image can be generated."""
    img = generate_tag_image("tag36h11", 1, size_pixels=100)
    assert img is not None
    # Size snaps to nearest multiple of grid_size (8): 100//8*8 = 96
    assert img.shape == (96, 96)
    assert img.dtype == "uint8"
    # Check that it's not all one color
    assert len(set(img.flatten())) > 1


def test_generate_aruco():
    """Verify that an ArUco image can be generated."""
    img = generate_tag_image("DICT_4X4_50", 42, size_pixels=100)
    assert img is not None
    # DICT_4X4 has grid_size=6, so 100//6*6 = 96
    assert img.shape == (96, 96)
    # Check that it's not all one color
    assert len(set(img.flatten())) > 1


def test_ensure_tag_asset(tmp_path):
    """Verify that ensure_tag_asset creates a file."""
    asset_dir = tmp_path / "tags"
    asset_path = ensure_tag_asset("tag36h11", 5, asset_dir, size_pixels=64)

    assert asset_path.exists()
    assert asset_path.name == "tag36h11_5_m0.png"

    # Load and verify
    img = cv2.imread(str(asset_path), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    assert img.shape == (64, 64)


def test_unsupported_family():
    """Verify that unsupported families return None."""
    img = generate_tag_image("invalid_family", 0)
    assert img is None
