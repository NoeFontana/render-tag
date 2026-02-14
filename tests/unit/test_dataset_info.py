import json

import pytest

from render_tag.audit.dataset_info import generate_dataset_info
from render_tag.core.config import EvaluationScope, GenConfig


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


def test_generate_dataset_info_modern(sample_dataset):
    # Setup a mock config
    config = GenConfig()

    # Test new 'evaluation_scopes' pattern
    info = generate_dataset_info(
        dataset_dir=sample_dataset,
        config=config,
        evaluation_scopes=[EvaluationScope.DETECTION, EvaluationScope.POSE_ACCURACY],
        extra_metadata={"custom": "value"},
    )

    # Check fields (Pydantic model access)
    assert EvaluationScope.DETECTION in info.evaluation_scopes
    assert EvaluationScope.POSE_ACCURACY in info.evaluation_scopes
    assert info.provenance.render_tag_version is not None
    assert info.metadata["custom"] == "value"
    assert info.pose_convention == "xyzw"

    # Verify file written (it's now manifest.json per the implementation)
    info_file = sample_dataset / "manifest.json"
    assert info_file.exists()

    saved_data = json.loads(info_file.read_text())
    assert "detection" in saved_data["evaluation_scopes"]
