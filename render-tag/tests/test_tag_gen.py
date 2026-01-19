from pathlib import Path
import os
import cv2
import pytest
from render_tag.tag_gen import generate_tag_image, ensure_tag_asset

def test_generate_apriltag():
    """Verify that an AprilTag image can be generated."""
    img = generate_tag_image("tag36h11", 1, size_pixels=100)
    assert img is not None
    assert img.shape == (100, 100)
    assert img.dtype == "uint8"
    # Check that it's not all one color
    assert len(set(img.flatten())) > 1

def test_generate_aruco():
    """Verify that an ArUco image can be generated."""
    img = generate_tag_image("DICT_4X4_50", 42, size_pixels=100)
    assert img is not None
    assert img.shape == (100, 100)
    # Check that it's not all one color
    assert len(set(img.flatten())) > 1

def test_ensure_tag_asset(tmp_path):
    """Verify that ensure_tag_asset creates a file."""
    asset_dir = tmp_path / "tags"
    asset_path = ensure_tag_asset("tag36h11", 5, asset_dir, size_pixels=64)
    
    assert asset_path.exists()
    assert asset_path.name == "tag36h11_5.png"
    
    # Load and verify
    img = cv2.imread(str(asset_path), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    assert img.shape == (64, 64)

def test_unsupported_family():
    """Verify that unsupported families return None."""
    img = generate_tag_image("invalid_family", 0)
    assert img is None
