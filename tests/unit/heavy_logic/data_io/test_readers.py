"""Tests for RenderTagDataset and CalibrationFrame readers."""

import json

import numpy as np
import pytest

from render_tag.core.schema.base import DetectionRecord
from render_tag.core.schema.board import BoardDefinition
from render_tag.data_io.readers import CalibrationFrame, RenderTagDataset


def _make_board_def():
    return BoardDefinition(
        type="charuco",
        rows=4,
        cols=4,
        square_size_mm=100.0,
        marker_size_mm=80.0,
        dictionary="tag36h11",
        total_keypoints=9,
    )


_UNSET = object()


def _make_board_record(image_id="img_0000", keypoints=_UNSET, board_def=None):
    if board_def is None:
        board_def = _make_board_def()
    if keypoints is _UNSET:
        # 9 saddle points for a 4x4 charuco: 3x3 interior intersections
        keypoints = [(100.0 + i * 10, 200.0 + i * 5) for i in range(9)]
    return DetectionRecord(
        image_id=image_id,
        tag_id=-1,
        tag_family="board_charuco",
        corners=[(320.0, 240.0)],
        record_type="BOARD",
        keypoints=keypoints,
        board_definition=board_def,
        k_matrix=[[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]],
        resolution=[640, 480],
    )


def _make_tag_record(image_id="img_0000", tag_id=0):
    return DetectionRecord(
        image_id=image_id,
        tag_id=tag_id,
        tag_family="tag36h11",
        corners=[(10, 10), (50, 10), (50, 50), (10, 50)],
        record_type="TAG",
    )


class TestRenderTagDatasetFromRecords:
    def test_image_ids(self):
        records = [
            _make_board_record("img_0000"),
            _make_tag_record("img_0000", tag_id=0),
            _make_board_record("img_0001"),
        ]
        ds = RenderTagDataset.from_records(records)
        assert ds.image_ids == ["img_0000", "img_0001"]

    def test_get_board_record(self):
        ds = RenderTagDataset.from_records([_make_board_record(), _make_tag_record()])
        board = ds.get_board_record("img_0000")
        assert board is not None
        assert board.record_type == "BOARD"

    def test_get_tag_records(self):
        records = [
            _make_board_record(),
            _make_tag_record(tag_id=0),
            _make_tag_record(tag_id=1),
        ]
        ds = RenderTagDataset.from_records(records)
        tags = ds.get_tag_records("img_0000")
        assert len(tags) == 2
        assert all(t.record_type == "TAG" for t in tags)

    def test_board_definition_property(self):
        ds = RenderTagDataset.from_records([_make_board_record()])
        bd = ds.board_definition
        assert bd is not None
        assert bd.rows == 4
        assert bd.cols == 4


class TestRenderTagDatasetFromJson:
    def test_load_new_format(self, tmp_path):
        record = _make_board_record()
        data = [record.model_dump(mode="json")]
        rich_truth = tmp_path / "rich_truth.json"
        rich_truth.write_text(json.dumps(data))

        ds = RenderTagDataset(tmp_path)
        assert len(ds.records) == 1
        assert ds.records[0].board_definition is not None
        assert ds.records[0].board_definition.type == "charuco"

    def test_load_old_format_migration(self, tmp_path):
        """Old format: board_definition nested inside metadata."""
        record = _make_board_record()
        data = record.model_dump(mode="json")
        # Move board_definition into metadata (old format)
        bd = data.pop("board_definition")
        data["metadata"]["board_definition"] = bd
        rich_truth = tmp_path / "rich_truth.json"
        rich_truth.write_text(json.dumps([data]))

        ds = RenderTagDataset(tmp_path)
        assert ds.records[0].board_definition is not None
        assert ds.records[0].board_definition.rows == 4

    def test_from_json_path(self, tmp_path):
        record = _make_board_record()
        path = tmp_path / "rich_truth.json"
        path.write_text(json.dumps([record.model_dump(mode="json")]))

        ds = RenderTagDataset.from_json(path)
        assert len(ds.records) == 1

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RenderTagDataset(tmp_path)


class TestIterCalibrationFrames:
    def test_yields_board_images_only(self):
        records = [
            _make_board_record("img_0000"),
            _make_tag_record("img_0000"),
            _make_tag_record("img_0001"),  # No board record
        ]
        ds = RenderTagDataset.from_records(records)
        frames = list(ds.iter_calibration_frames())
        assert len(frames) == 1
        assert frames[0].image_id == "img_0000"

    def test_get_calibration_frame(self):
        ds = RenderTagDataset.from_records([_make_board_record()])
        frame = ds.get_calibration_frame("img_0000")
        assert frame is not None
        assert frame.image_id == "img_0000"

    def test_get_calibration_frame_missing(self):
        ds = RenderTagDataset.from_records([_make_tag_record()])
        assert ds.get_calibration_frame("img_0000") is None


class TestCalibrationFrame:
    def test_board_definition_property(self):
        frame = CalibrationFrame("img_0000", _make_board_record())
        assert frame.board_definition.type == "charuco"

    def test_k_matrix(self):
        frame = CalibrationFrame("img_0000", _make_board_record())
        k = frame.k_matrix
        assert k.shape == (3, 3)
        assert k[0, 0] == 500.0

    def test_resolution(self):
        frame = CalibrationFrame("img_0000", _make_board_record())
        assert frame.resolution == (640, 480)


class TestGetValidCalibrationPairs:
    def test_all_visible(self):
        """All 9 keypoints visible — should return 9 matched pairs."""
        frame = CalibrationFrame("img_0000", _make_board_record())
        obj_pts, img_pts, ids = frame.get_valid_calibration_pairs()

        assert obj_pts.shape == (9, 3)
        assert img_pts.shape == (9, 2)
        assert ids.shape == (9,)
        assert np.array_equal(ids, np.arange(9, dtype=np.int32))

    def test_filters_sentinels(self):
        """Sentinel keypoints should be filtered out."""
        keypoints = [(100.0 + i * 10, 200.0 + i * 5) for i in range(9)]
        # Mark indices 2, 5, 7 as sentinel
        keypoints[2] = (-1.0, -1.0)
        keypoints[5] = (-1.0, -1.0)
        keypoints[7] = (-1.0, -1.0)

        record = _make_board_record(keypoints=keypoints)
        frame = CalibrationFrame("img_0000", record)
        obj_pts, img_pts, ids = frame.get_valid_calibration_pairs()

        assert obj_pts.shape == (6, 3)
        assert img_pts.shape == (6, 2)
        assert list(ids) == [0, 1, 3, 4, 6, 8]

    def test_index_alignment(self):
        """valid_ids must correspond to the correct 3D object points."""
        keypoints = [(100.0 + i * 10, 200.0 + i * 5) for i in range(9)]
        keypoints[0] = (-1.0, -1.0)  # Sentinel at index 0

        record = _make_board_record(keypoints=keypoints)
        frame = CalibrationFrame("img_0000", record)
        _obj_pts, img_pts, ids = frame.get_valid_calibration_pairs()

        assert ids[0] == 1  # First valid is index 1
        # The 2D point at ids[0]=1 should match keypoints[1]
        assert img_pts[0, 0] == pytest.approx(110.0)
        assert img_pts[0, 1] == pytest.approx(205.0)

    def test_no_keypoints(self):
        record = _make_board_record(keypoints=None)
        frame = CalibrationFrame("img_0000", record)
        obj_pts, img_pts, ids = frame.get_valid_calibration_pairs()
        assert obj_pts.shape == (0, 3)
        assert img_pts.shape == (0, 2)
        assert ids.shape == (0,)

    def test_all_sentinels(self):
        keypoints = [(-1.0, -1.0)] * 9
        record = _make_board_record(keypoints=keypoints)
        frame = CalibrationFrame("img_0000", record)
        obj_pts, _img_pts, ids = frame.get_valid_calibration_pairs()
        assert obj_pts.shape == (0, 3)
        assert ids.shape == (0,)


class TestGetAllKeypointsWithVisibility:
    def test_all_visible(self):
        frame = CalibrationFrame("img_0000", _make_board_record())
        kp, vis = frame.get_all_keypoints_with_visibility()
        assert kp.shape == (9, 2)
        assert vis.shape == (9,)
        assert np.all(vis)

    def test_mixed_visibility(self):
        keypoints = [(100.0 + i * 10, 200.0 + i * 5) for i in range(9)]
        keypoints[3] = (-1.0, -1.0)
        keypoints[6] = (-1.0, -1.0)

        record = _make_board_record(keypoints=keypoints)
        frame = CalibrationFrame("img_0000", record)
        kp, vis = frame.get_all_keypoints_with_visibility()

        assert kp.shape == (9, 2)
        assert vis[3] is np.bool_(False)
        assert vis[6] is np.bool_(False)
        assert np.sum(vis) == 7

    def test_no_keypoints(self):
        record = _make_board_record(keypoints=None)
        frame = CalibrationFrame("img_0000", record)
        kp, vis = frame.get_all_keypoints_with_visibility()
        assert kp.shape == (9, 2)  # total_keypoints from board_definition
        assert np.all(~vis)
