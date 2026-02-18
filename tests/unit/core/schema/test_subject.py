import pytest
from pydantic import ValidationError

from render_tag.core.schema.subject import BoardSubjectConfig, SubjectConfig, TagSubjectConfig


def test_tag_subject_config_valid():
    config = TagSubjectConfig(
        tag_families=["tag36h11"],
        size_meters=0.1,
        tags_per_scene=10
    )
    assert config.type == "TAGS"
    assert config.tag_families == ["tag36h11"]

def test_board_subject_config_valid_charuco():
    config = BoardSubjectConfig(
        type="BOARD",
        rows=5,
        cols=8,
        marker_size=0.04,
        square_size=0.05,
        dictionary="tag36h11"
    )
    assert config.type == "BOARD"
    assert config.rows == 5

def test_board_subject_config_valid_aprilgrid():
    config = BoardSubjectConfig(
        type="BOARD",
        rows=6,
        cols=6,
        marker_size=0.08,
        spacing_ratio=0.3,
        dictionary="tagStandard41h12"
    )
    assert config.type == "BOARD"

def test_subject_config_polymorphism():
    # Test TAGS
    data_tags = {
        "type": "TAGS",
        "tag_families": ["tag16h5"],
        "size_meters": 0.05
    }
    subject_tags = SubjectConfig.model_validate(data_tags)
    assert isinstance(subject_tags.root, TagSubjectConfig)
    
    # Test BOARD
    data_board = {
        "type": "BOARD",
        "rows": 4,
        "cols": 4,
        "marker_size": 0.02,
        "square_size": 0.03
    }
    subject_board = SubjectConfig.model_validate(data_board)
    assert isinstance(subject_board.root, BoardSubjectConfig)

def test_subject_config_invalid_type():
    with pytest.raises(ValidationError):
        SubjectConfig.model_validate({"type": "INVALID", "data": 123})

def test_board_constraints_violated():
    # marker_size >= square_size for ChArUco
    with pytest.raises(ValidationError):
        BoardSubjectConfig(
            type="BOARD",
            rows=5,
            cols=5,
            marker_size=0.1,
            square_size=0.08
        )
