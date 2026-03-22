"""Tests for BoardDefinition Pydantic model."""

import pytest
from pydantic import ValidationError

from render_tag.core.schema.base import DetectionRecord
from render_tag.core.schema.board import BoardDefinition, BoardType


def _make_charuco_def(**overrides):
    defaults = {
        "type": "charuco",
        "rows": 4,
        "cols": 4,
        "square_size_mm": 100.0,
        "marker_size_mm": 80.0,
        "dictionary": "tag36h11",
        "total_keypoints": 9,
    }
    defaults.update(overrides)
    return BoardDefinition(**defaults)


def _make_aprilgrid_def(**overrides):
    defaults = {
        "type": "aprilgrid",
        "rows": 2,
        "cols": 7,
        "square_size_mm": 60.0,
        "marker_size_mm": 50.0,
        "dictionary": "tag36h11",
        "total_keypoints": 14,
        "spacing_ratio": 0.2,
    }
    defaults.update(overrides)
    return BoardDefinition(**defaults)


class TestBoardDefinitionConstruction:
    def test_charuco_valid(self):
        bd = _make_charuco_def()
        assert bd.type == BoardType.CHARUCO
        assert bd.rows == 4
        assert bd.cols == 4
        assert bd.square_size_mm == 100.0
        assert bd.marker_size_mm == 80.0
        assert bd.dictionary == "tag36h11"
        assert bd.total_keypoints == 9
        assert bd.spacing_ratio is None

    def test_aprilgrid_valid(self):
        bd = _make_aprilgrid_def()
        assert bd.type == BoardType.APRILGRID
        assert bd.spacing_ratio == 0.2

    def test_aprilgrid_requires_spacing_ratio(self):
        with pytest.raises(ValidationError, match="spacing_ratio"):
            _make_aprilgrid_def(spacing_ratio=None)

    def test_charuco_no_spacing_ratio_ok(self):
        bd = _make_charuco_def(spacing_ratio=None)
        assert bd.spacing_ratio is None

    def test_invalid_square_size(self):
        with pytest.raises(ValidationError):
            _make_charuco_def(square_size_mm=-1.0)

    def test_invalid_marker_size(self):
        with pytest.raises(ValidationError):
            _make_charuco_def(marker_size_mm=0.0)


class TestBoardDefinitionSerialization:
    def test_roundtrip(self):
        bd = _make_charuco_def()
        dumped = bd.model_dump(mode="json")
        restored = BoardDefinition.model_validate(dumped)
        assert restored == bd

    def test_aprilgrid_roundtrip(self):
        bd = _make_aprilgrid_def()
        dumped = bd.model_dump(mode="json")
        restored = BoardDefinition.model_validate(dumped)
        assert restored == bd
        assert restored.spacing_ratio == 0.2

    def test_json_shape(self):
        bd = _make_charuco_def()
        dumped = bd.model_dump(mode="json")
        assert isinstance(dumped, dict)
        assert dumped["type"] == "charuco"
        assert "spacing_ratio" in dumped


class TestDetectionRecordBoardField:
    def test_board_record_carries_definition(self):
        bd = _make_charuco_def()
        record = DetectionRecord(
            image_id="test_img",
            tag_id=-1,
            tag_family="board_charuco",
            corners=[(100.0, 100.0)],
            record_type="BOARD",
            board_definition=bd,
        )
        assert record.board_definition is not None
        assert record.board_definition.type == BoardType.CHARUCO
        assert record.board_definition.rows == 4

    def test_tag_record_no_definition(self):
        record = DetectionRecord(
            image_id="test_img",
            tag_id=0,
            tag_family="tag36h11",
            corners=[(0, 0), (1, 0), (1, 1), (0, 1)],
            record_type="TAG",
        )
        assert record.board_definition is None

    def test_board_definition_serialized_in_model_dump(self):
        bd = _make_charuco_def()
        record = DetectionRecord(
            image_id="test_img",
            tag_id=-1,
            tag_family="board_charuco",
            corners=[(100.0, 100.0)],
            record_type="BOARD",
            board_definition=bd,
        )
        dumped = record.model_dump(mode="json")
        assert "board_definition" in dumped
        assert dumped["board_definition"]["type"] == "charuco"
        assert dumped["board_definition"]["rows"] == 4
