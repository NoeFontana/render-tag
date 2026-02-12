import json

import pytest

from render_tag.audit.dataset_info import generate_dataset_info


@pytest.fixture
def sample_dataset(tmp_path):
    # Create a mock dataset structure
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "0000.png").write_text("fake image data")

    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()
    (annotations_dir / "0000.json").write_text('{"foo": "bar"}')

    return tmp_path


def test_generate_dataset_info_legacy(sample_dataset):
    # Test backward compatibility with 'intent'
    info = generate_dataset_info(
        dataset_dir=sample_dataset,
        intent="calibration",
        geometry={"tag_size_m": 0.16},
    )

    assert info["intent"] == "calibration"
    assert info["evaluation_scopes"] == ["calibration"]


def test_generate_dataset_info_modern(sample_dataset):
    # Test new 'evaluation_scopes' pattern
    info = generate_dataset_info(
        dataset_dir=sample_dataset,
        evaluation_scopes=["detection", "pose_estimation"],
        extra_metadata={"custom": "value"},
    )

    # Check fields
    assert "detection" in info["evaluation_scopes"]
    assert "pose_estimation" in info["evaluation_scopes"]
    assert info["intent"] == "detection"  # Fallback intent
    assert info["provenance"]["render_tag_version"] is not None
    assert info["integrity"]["sha256"] is not None
    assert info["metadata"]["custom"] == "value"
    assert info["provenance"]["pose_convention"] == "xyzw"

    # Verify file written
    info_file = sample_dataset / "dataset_info.json"
    assert info_file.exists()

    saved_data = json.loads(info_file.read_text())
    assert "detection" in saved_data["evaluation_scopes"]
