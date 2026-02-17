
import pytest
from pydantic import ValidationError
from render_tag.core.schema.board import BoardConfig, BoardType

def test_board_config_aprilgrid():
    """Verify AprilGrid configuration parsing."""
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=6,
        cols=6,
        marker_size=0.08,
        spacing_ratio=0.3,
        dictionary="tag36h11"
    )
    assert config.type == BoardType.APRILGRID
    assert config.rows == 6
    assert config.cols == 6
    assert config.marker_size == 0.08
    assert config.spacing_ratio == 0.3
    assert config.dictionary == "tag36h11"

def test_board_config_charuco():
    """Verify ChArUco configuration parsing."""
    config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=5,
        cols=7,
        square_size=0.04,
        marker_size=0.03,
        dictionary="DICT_4X4_50"
    )
    assert config.type == BoardType.CHARUCO
    assert config.rows == 5
    assert config.cols == 7
    assert config.square_size == 0.04
    assert config.marker_size == 0.03
    assert config.dictionary == "DICT_4X4_50"

def test_board_config_validation():
    """Verify basic validation for board config."""
    with pytest.raises(ValidationError):
        # Rows must be positive
        BoardConfig(type=BoardType.APRILGRID, rows=0, cols=6, marker_size=0.08)
    
    with pytest.raises(ValidationError):
        # Cols must be positive
        BoardConfig(type=BoardType.APRILGRID, rows=6, cols=-1, marker_size=0.08)

    with pytest.raises(ValidationError):
        # marker_size must be positive
        BoardConfig(type=BoardType.APRILGRID, rows=6, cols=6, marker_size=0.0)
