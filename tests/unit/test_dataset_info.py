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


def test_generate_dataset_info(sample_dataset):
    # Test generation of dataset_info.json

    info = generate_dataset_info(
        dataset_dir=sample_dataset,
        intent="calibration",
        geometry={"tag_size_m": 0.16},
        extra_metadata={"custom": "value"},
    )

    # Check fields
    assert info["intent"] == "calibration"
    assert info["geometry"]["tag_size_m"] == 0.16
    assert info["provenance"]["render_tag_version"] is not None
    assert info["integrity"]["sha256"] is not None
    assert len(info["integrity"]["sha256"]) == 64
    assert info["metadata"]["custom"] == "value"

    # Verify file written
    info_file = sample_dataset / "dataset_info.json"
    assert info_file.exists()

    saved_data = json.loads(info_file.read_text())
    assert saved_data["intent"] == "calibration"
