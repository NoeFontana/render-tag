import pytest
from pydantic import ValidationError

from render_tag.core.metadata import DatasetManifest


def test_dataset_metadata_valid():
    """Verify that a valid metadata passes validation."""
    data = {
        "camera_intrinsics": {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 640.0,
            "cy": 360.0,
            "width": 1280,
            "height": 720,
        },
        "tag_specification": {"tag_family": "tag36h11", "tag_size_m": 0.160},
        "pose_convention": "wxyz",
    }
    manifest = DatasetManifest(**data)
    assert manifest.pose_convention == "wxyz"
    assert manifest.tag_specification.tag_size_m == 0.160


def test_dataset_metadata_invalid_tag_size_legacy():
    """Verify that tag_size_mm is no longer allowed."""
    data = {
        "camera_intrinsics": {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 640.0,
            "cy": 360.0,
            "width": 1280,
            "height": 720,
        },
        "tag_specification": {
            "tag_family": "tag36h11",
            "tag_size_mm": 160,  # Old field
        },
        "pose_convention": "wxyz",
    }
    with pytest.raises(ValidationError):
        DatasetManifest(**data)


def test_dataset_metadata_invalid_convention():
    """Verify that only 'wxyz' is allowed."""
    data = {
        "camera_intrinsics": {
            "fx": 1000.0,
            "fy": 1000.0,
            "cx": 640.0,
            "cy": 360.0,
            "width": 1280,
            "height": 720,
        },
        "tag_specification": {"tag_family": "tag36h11", "tag_size_m": 0.160},
        "pose_convention": "xyzw",  # Invalid (legacy format)
    }
    with pytest.raises(ValidationError):
        DatasetManifest(**data)
