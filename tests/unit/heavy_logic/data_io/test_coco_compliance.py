import json

import numpy as np
import pytest

from render_tag.core.schema.base import DetectionRecord
from render_tag.data_io.annotations import compute_dense_distorted_polygon, compute_eval_visibility
from render_tag.data_io.writers import COCOWriter


@pytest.fixture
def kb_detection():
    """DetectionRecord with KB pose info for a 10cm tag at 1 m depth, centered."""
    return DetectionRecord(
        image_id="img1",
        tag_id=1,
        tag_family="tag36h11",
        # Pinhole-projected corners for a 100mm tag at 1m, fx=fy=640, cx=320, cy=240.
        # These satisfy CW winding order in image (Y-down) space.
        corners=[(288.0, 208.0), (352.0, 208.0), (352.0, 272.0), (288.0, 272.0)],
        record_type="TAG",
        position=[0.0, 0.0, 1.0],
        rotation_quaternion=[1.0, 0.0, 0.0, 0.0],
        k_matrix=[[640.0, 0.0, 320.0], [0.0, 640.0, 240.0], [0.0, 0.0, 1.0]],
        tag_size_mm=100.0,
        distortion_model="kannala_brandt",
        distortion_coeffs=[0.1, 0.01, 0.001, 0.0001],
    )


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
                [5, 500],  # left margin  → False
                [500, 5],  # top margin   → False
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


class TestKBFisheyeAnnotations:
    """KB-fisheye-specific annotation correctness tests."""

    def test_out_of_image_corner_gets_v1_with_zero_margin(self):
        """Corner projected outside image bounds is v=1, not v=2, even at margin=0."""
        points = np.array([[-5.0, 100.0], [320.0, 240.0]], dtype=float)
        vis = compute_eval_visibility(points, width=640, height=480, margin_px=0)
        assert not vis[0], "out-of-image corner (x<0) must be v=1, not v=2"
        assert vis[1], "interior corner must remain v=2"

    def test_boundary_pixel_is_visible_with_zero_margin(self):
        """Corner exactly at (0, 0) is in-image and gets v=2 with margin=0."""
        points = np.array([[0.0, 0.0], [639.0, 479.0]], dtype=float)
        vis = compute_eval_visibility(points, width=640, height=480, margin_px=0)
        assert vis[0]
        assert vis[1]

    def test_just_outside_right_edge_gets_v1(self):
        """Corner at exactly x=width is outside the image and gets v=1."""
        points = np.array([[640.0, 240.0]], dtype=float)
        vis = compute_eval_visibility(points, width=640, height=480, margin_px=0)
        assert not vis[0]

    def test_dense_polygon_kb_has_more_than_4_points(self, kb_detection):
        """KB dense polygon contains more than 4 vertices."""
        poly = compute_dense_distorted_polygon(
            kb_detection, kb_detection.distortion_coeffs, "kannala_brandt"
        )
        assert poly is not None
        assert len(poly) > 4

    def test_dense_polygon_any_model_with_pose_works(self, kb_detection):
        """Dense polygon works for any distortion model when pose is available.
        The KB-only gate lives in add_annotation(), not in this helper."""
        poly = compute_dense_distorted_polygon(
            kb_detection, [0.1, 0.01, 0.0, 0.0, 0.001], "brown_conrady"
        )
        assert poly is not None
        assert len(poly) > 4

    def test_dense_polygon_no_pose_returns_none(self):
        """Dense polygon returns None when detection lacks 3D pose info."""
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            corners=[(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)],
            record_type="TAG",
        )
        poly = compute_dense_distorted_polygon(det, [0.1, 0.01, 0.001, 0.0001], "kannala_brandt")
        assert poly is None

    def test_coco_writer_kb_segmentation_is_dense(self, tmp_path, kb_detection):
        """COCOWriter produces a dense segmentation polygon for KB annotations."""
        writer = COCOWriter(tmp_path)
        img_id = writer.add_image("img.png", 640, 480)
        cat_id = writer.add_category("tag36h11")
        writer.add_annotation(img_id, cat_id, kb_detection.corners, 640, 480, kb_detection)
        with open(writer.save()) as f:
            data = json.load(f)
        seg = data["annotations"][0]["segmentation"]
        assert len(seg) == 1, "exactly one polygon"
        n_vertices = len(seg[0]) // 2
        assert n_vertices > 4, f"expected dense polygon, got {n_vertices} vertices"

    def test_coco_writer_kb_bbox_uses_dense_points(self, tmp_path, kb_detection):
        """COCOWriter bbox for KB is derived from dense polygon, not just 4 corners.

        The dense-polygon bbox differs from the naive 4-corner pinhole bbox because
        KB distortion shifts each projected pixel position.  We verify:
        1. The bbox is non-zero and plausible.
        2. It is derived from the dense polygon (matches compute_dense_distorted_polygon).
        """
        from render_tag.data_io.annotations import compute_dense_distorted_polygon

        writer = COCOWriter(tmp_path)
        img_id = writer.add_image("img.png", 640, 480)
        cat_id = writer.add_category("tag36h11")
        writer.add_annotation(img_id, cat_id, kb_detection.corners, 640, 480, kb_detection)
        with open(writer.save()) as f:
            data = json.load(f)
        ann = data["annotations"][0]
        bbox = ann["bbox"]

        # Compute the expected bbox from dense polygon directly.
        dense_poly = compute_dense_distorted_polygon(
            kb_detection, kb_detection.distortion_coeffs, "kannala_brandt"
        )
        assert dense_poly is not None
        import numpy as np

        dense_arr = np.array(dense_poly)
        exp_x_min = float(np.min(dense_arr[:, 0]))
        exp_y_min = float(np.min(dense_arr[:, 1]))
        exp_w = float(np.max(dense_arr[:, 0])) - exp_x_min
        exp_h = float(np.max(dense_arr[:, 1])) - exp_y_min

        assert bbox[0] == pytest.approx(exp_x_min, abs=1e-6), "x_min must match dense polygon"
        assert bbox[1] == pytest.approx(exp_y_min, abs=1e-6), "y_min must match dense polygon"
        assert bbox[2] == pytest.approx(exp_w, abs=1e-6), "width must match dense polygon"
        assert bbox[3] == pytest.approx(exp_h, abs=1e-6), "height must match dense polygon"
        # The dense bbox must be non-degenerate.
        assert bbox[2] > 0 and bbox[3] > 0

    def test_coco_writer_extra_keypoints_margin_zone_v1(self, tmp_path):
        """Calibration saddle points within eval_margin_px zone get v=1, not v=2."""
        det = DetectionRecord(
            image_id="img1",
            tag_id=0,
            tag_family="board_aprilgrid",
            corners=[(500.0, 300.0)],  # single board-center point
            keypoints=[
                (5.0, 300.0),  # left margin (x < 10)  → v=1
                (500.0, 300.0),  # interior              → v=2
                (-1.0, -1.0),  # sentinel              → v=0
            ],
            record_type="BOARD",
            eval_margin_px=10,
        )
        writer = COCOWriter(tmp_path, eval_margin_px=10)
        img_id = writer.add_image("img.png", 640, 480)
        cat_id = writer.add_category("board_aprilgrid")
        writer.add_annotation(img_id, cat_id, det.corners, 640, 480, det)
        with open(writer.save()) as f:
            data = json.load(f)
        kp = data["annotations"][0]["keypoints"]
        # Corners are a single point (board center), not 4 → no corners keypoints block.
        # Extra keypoints start at offset 1*3 = 3 (after the single board-center point).
        extra_v = [kp[3 + i * 3 + 2] for i in range(3)]
        assert extra_v[0] == 1, "margin-zone saddle point must be v=1"
        assert extra_v[1] == 2, "interior saddle point must be v=2"
        assert extra_v[2] == 0, "sentinel keypoint must be v=0"

    def test_coco_writer_out_of_image_corner_v1(self, tmp_path):
        """A corner projected outside the image frame gets v=1, not v=2."""
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            # Three corners inside image, one (TL) just outside the left boundary.
            # Winding validator skips invalid points (very negative x).
            corners=[(-5.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)],
            record_type="TAG",
        )
        writer = COCOWriter(tmp_path)
        img_id = writer.add_image("img.png", 640, 480)
        cat_id = writer.add_category("tag36h11")
        writer.add_annotation(img_id, cat_id, det.corners, 640, 480, det)
        with open(writer.save()) as f:
            data = json.load(f)
        kp = data["annotations"][0]["keypoints"]
        v_flags = [kp[i * 3 + 2] for i in range(4)]
        assert v_flags[0] == 1, "corner at x=-5 must be v=1 (not visible)"
        assert all(v == 2 for v in v_flags[1:]), "in-image corners must be v=2"


class TestAdaptivePolygon:
    """Tests for compute_dense_distorted_polygon adaptive subdivision."""

    def _make_det(self, tag_size_mm=100.0, z=1.0):
        """Minimal detection with a KB fisheye camera at z=1m, tag facing camera."""
        from types import SimpleNamespace

        # Identity rotation, tag centred on optical axis
        return SimpleNamespace(
            position=[0.0, 0.0, float(z)],
            rotation_quaternion=[1.0, 0.0, 0.0, 0.0],  # w,x,y,z
            k_matrix=[[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]],
            tag_size_mm=float(tag_size_mm),
            record_type="TAG",
        )

    def test_tighter_threshold_yields_more_vertices(self):
        """A tighter max_error_px must produce >= as many vertices as a looser one."""
        dist_coeffs = [0.3, 0.05, 0.001, 0.0]
        det = self._make_det(tag_size_mm=200.0, z=0.5)

        pts_loose = compute_dense_distorted_polygon(
            det, dist_coeffs, "kannala_brandt", max_error_px=2.0
        )
        pts_tight = compute_dense_distorted_polygon(
            det, dist_coeffs, "kannala_brandt", max_error_px=0.25
        )
        assert pts_loose is not None and pts_tight is not None
        assert len(pts_tight) >= len(pts_loose), (
            f"tighter threshold ({len(pts_tight)} pts) should produce >= vertices "
            f"than loose ({len(pts_loose)} pts)"
        )

    def test_strong_distortion_triggers_subdivision(self):
        """Strong KB distortion must trigger at least one subdivision per edge (> 5 minimum)."""
        dist_coeffs = [0.3, 0.05, 0.001, 0.0]  # strong KB
        det = self._make_det(tag_size_mm=300.0, z=0.4)

        pts = compute_dense_distorted_polygon(det, dist_coeffs, "kannala_brandt", max_error_px=0.5)
        assert pts is not None
        # Minimum is 5 (1 initial vertex + 1 endpoint per edge, 4 edges).
        # Strong distortion must cause at least one edge to subdivide.
        assert len(pts) > 5, f"expected subdivision for strong distortion, got {len(pts)} points"

    def test_no_distortion_returns_minimal_points(self):
        """With zero distortion coefficients, edges are already straight — minimal subdivision."""
        det = self._make_det(tag_size_mm=100.0, z=1.0)
        pts = compute_dense_distorted_polygon(det, [0.0, 0.0, 0.0, 0.0], "kannala_brandt", 0.5)
        assert pts is not None
        # Without curvature each edge needs only 2 points (start + end), so ≤ 4*2 = 8 total
        assert len(pts) <= 8, f"expected minimal vertices for zero distortion, got {len(pts)}"

    def test_returns_none_without_pose(self):
        """Returns None when position is missing (caller falls back to 4-corner polygon)."""
        from types import SimpleNamespace

        det = SimpleNamespace(
            position=None,
            rotation_quaternion=None,
            k_matrix=None,
            tag_size_mm=100.0,
            record_type="TAG",
        )
        assert compute_dense_distorted_polygon(det, [0.1], "kannala_brandt") is None
