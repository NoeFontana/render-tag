import pytest
from pydantic import ValidationError

from render_tag.orchestration.experiment_schema import DatasetManifest


def test_dataset_manifest_valid():
    """Verify that a valid manifest passes validation."""
    data = {
        "camera_intrinsics": {
            "focal_length_px": [1000.0, 1000.0],
            "principal_point": [640.0, 360.0],
            "resolution": [1280, 720],
        },
        "tag_specification": {"tag_family": "tag36h11", "tag_size_m": 0.160},
        "pose_convention": "wxyz",
        "sweep_definition": {"variable_name": "distance", "range": [1.0, 30.0]},
    }
    manifest = DatasetManifest(**data)
    assert manifest.pose_convention == "wxyz"
    assert manifest.tag_specification.tag_size_m == 0.160


def test_dataset_manifest_invalid_tag_size_legacy():
    """Verify that tag_size_mm is no longer allowed."""
    data = {
        "camera_intrinsics": {
            "focal_length_px": [1000.0, 1000.0],
            "principal_point": [640.0, 360.0],
            "resolution": [1280, 720],
        },
        "tag_specification": {
            "tag_family": "tag36h11",
            "tag_size_mm": 160,  # Old field
        },
        "pose_convention": "wxyz",
    }
    with pytest.raises(ValidationError):
        DatasetManifest(**data)


def test_dataset_manifest_invalid_convention():
    """Verify that only 'wxyz' is allowed for now."""
    data = {
        "camera_intrinsics": {
            "focal_length_px": [1000.0, 1000.0],
            "principal_point": [640.0, 360.0],
            "resolution": [1280, 720],
        },
        "tag_specification": {"tag_family": "tag36h11", "tag_size_m": 0.160},
        "pose_convention": "xyzw",  # Invalid
    }
    with pytest.raises(ValidationError):
        DatasetManifest(**data)
