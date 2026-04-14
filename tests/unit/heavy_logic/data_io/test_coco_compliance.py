import json

import numpy as np
import pytest

from render_tag.core.schema.base import DetectionRecord
from render_tag.data_io.annotations import compute_eval_visibility
from render_tag.data_io.writers import COCOWriter


def test_coco_keypoint_compliance_tag(tmp_path):
    writer = COCOWriter(tmp_path)

    det = DetectionRecord(
        image_id="img1",
        tag_id=1,
        tag_family="tag36h11",
        corners=[(10, 10), (20, 10), (20, 20), (10, 20)],
        record_type="TAG",
    )

    cat_id = writer.add_category("tag36h11")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, det.corners, detection=det)

    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)

    ann = data["annotations"][0]
    # COCO Keypoints: [x1, y1, v1, x2, y2, v2, ...]
    # v=2 means visible and labeled
    assert len(ann["keypoints"]) == 4 * 3
    assert ann["num_keypoints"] == 4
    for i in range(4):
        assert ann["keypoints"][i * 3 + 2] == 2


def test_coco_keypoint_compliance_subject(tmp_path):
    writer = COCOWriter(tmp_path)

    # Subject with 4 corners and 2 extra keypoints (e.g. saddle points)
    det = DetectionRecord(
        image_id="img1",
        tag_id=0,
        tag_family="board",
        corners=[(0, 0), (100, 0), (100, 100), (0, 100)],
        keypoints=[(50, 50), (60, 60)],
        record_type="SUBJECT",
    )

    cat_id = writer.add_category("board")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, det.corners, detection=det)

    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)

    ann = data["annotations"][0]
    # 4 corners + 2 keypoints = 6 total
    assert len(ann["keypoints"]) == 6 * 3
    assert ann["num_keypoints"] == 6
    assert ann["attributes"]["record_type"] == "SUBJECT"


def test_coco_single_point_box(tmp_path):
    writer = COCOWriter(tmp_path)

    # Only one point (e.g. a single saddle point record if we exported that way)
    # COCOWriter handles < 3 points by creating a tiny box
    corners = [(50.0, 50.0)]

    cat_id = writer.add_category("point")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, corners)

    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)

    ann = data["annotations"][0]
    # Bbox: [x, y, w, h]
    # For single point at (50, 50), box should be [49.5, 49.5, 1.0, 1.0]
    assert ann["bbox"] == [49.5, 49.5, 1.0, 1.0]
    assert ann["area"] == 1.0


class TestEvalMargin:
    def test_compute_eval_visibility_no_margin(self):
        """With margin=0 all in-image points are visible."""
        points = np.array([[0, 0], [999, 999], [500, 500]], dtype=float)
        vis = compute_eval_visibility(points, width=1000, height=1000, margin_px=0)
        assert list(vis) == [True, True, True]

    def test_compute_eval_visibility_with_margin(self):
        """Points inside the margin zone are flagged False; interior points True."""
        W, H, M = 1000, 1000, 10
        points = np.array(
            [
                [5, 500],    # left margin  → False
                [500, 5],    # top margin   → False
                [995, 500],  # right margin → False
                [500, 995],  # bottom margin → False
                [500, 500],  # interior     → True
            ],
            dtype=float,
        )
        vis = compute_eval_visibility(points, W, H, M)
        assert list(vis) == [False, False, False, False, True]

    def test_compute_eval_visibility_sentinel(self):
        """Sentinel points (-1, -1) remain False even with margin=0."""
        points = np.array([[-1, -1], [500, 500]], dtype=float)
        vis = compute_eval_visibility(points, width=1000, height=1000, margin_px=0)
        assert list(vis) == [False, True]

    def test_coco_writer_eval_margin_v_flags(self, tmp_path):
        """COCOWriter with eval_margin_px assigns v=1 to margin-zone corners."""
        writer = COCOWriter(tmp_path, eval_margin_px=10)
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            # Corners: 3 in margin zone, 1 interior — must be CW winding
            corners=[(5, 5), (995, 5), (995, 995), (5, 995)],
            record_type="TAG",
        )
        cat_id = writer.add_category("tag36h11")
        img_id = writer.add_image("img1.png", 1000, 1000)
        writer.add_annotation(img_id, cat_id, det.corners, width=1000, height=1000, detection=det)

        with open(writer.save()) as f:
            data = json.load(f)
        ann = data["annotations"][0]
        v_flags = [ann["keypoints"][i * 3 + 2] for i in range(4)]
        # All 4 corners are within the 10px margin
        assert all(v == 1 for v in v_flags)

    def test_coco_writer_no_margin_all_visible(self, tmp_path):
        """COCOWriter with eval_margin_px=0 (default) assigns v=2 to all corners."""
        writer = COCOWriter(tmp_path, eval_margin_px=0)
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            corners=[(10, 10), (90, 10), (90, 90), (10, 90)],
            record_type="TAG",
        )
        cat_id = writer.add_category("tag36h11")
        img_id = writer.add_image("img1.png", 640, 480)
        writer.add_annotation(img_id, cat_id, det.corners, width=640, height=480, detection=det)

        with open(writer.save()) as f:
            data = json.load(f)
        ann = data["annotations"][0]
        v_flags = [ann["keypoints"][i * 3 + 2] for i in range(4)]
        assert all(v == 2 for v in v_flags)

    def test_coco_writer_bbox_unaffected_by_margin(self, tmp_path):
        """Bounding box always spans the full tag polygon, ignoring the margin."""
        writer = COCOWriter(tmp_path, eval_margin_px=50)
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            corners=[(5, 5), (995, 5), (995, 995), (5, 995)],
            record_type="TAG",
        )
        cat_id = writer.add_category("tag36h11")
        img_id = writer.add_image("img1.png", 1000, 1000)
        writer.add_annotation(img_id, cat_id, det.corners, width=1000, height=1000, detection=det)

        with open(writer.save()) as f:
            data = json.load(f)
        ann = data["annotations"][0]
        x, y, w, h = ann["bbox"]
        assert x == pytest.approx(5.0)
        assert y == pytest.approx(5.0)
        assert w == pytest.approx(990.0)
        assert h == pytest.approx(990.0)
