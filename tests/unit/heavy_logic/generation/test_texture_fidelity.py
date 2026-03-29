"""Null-space fidelity tests: visual saddle points must match projected GT.

These tests verify that the texture synthesis pipeline produces images whose
visual corner/saddle-point locations match the mathematically computed grid
intersection positions to sub-pixel precision.  This is the critical contract
for downstream calibration detectors (cornerSubPix, Kalibr, etc.).
"""

import cv2
import numpy as np

from render_tag.core.schema.board import BoardConfig, BoardType
from render_tag.generation.texture_factory import TextureFactory


def _grid_intersection_points(
    config: BoardConfig, factory: TextureFactory
) -> list[tuple[float, float]]:
    """Return OpenCV continuous coordinates of every interior grid intersection.

    Uses ``factory.compute_grid_metrics`` as the single source of truth,
    then applies the -0.5 shift to convert array indices to continuous
    coordinates (the visual edge between pixel ``sq-1`` and ``sq`` is at
    ``sq - 0.5`` in OpenCV's convention where pixel centers are at integers).
    """
    gm = factory.compute_grid_metrics(config)

    pts: list[tuple[float, float]] = []
    for r in range(1, config.rows):
        for c in range(1, config.cols):
            y_idx = r * gm.square_px + gm.quiet_zone_px
            x_idx = c * gm.square_px + gm.quiet_zone_px
            pts.append((float(x_idx) - 0.5, float(y_idx) - 0.5))
    return pts


def test_charuco_saddle_point_fidelity():
    """ChArUco interior saddle points must be recoverable to < 0.1 px."""
    config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=6,
        cols=8,
        square_size=0.04,
        marker_size=0.03,
        dictionary="DICT_4X4_50",
    )
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    gt_pts = _grid_intersection_points(config, factory)
    assert len(gt_pts) == (config.rows - 1) * (config.cols - 1)

    corners = cv2.goodFeaturesToTrack(
        img,
        maxCorners=len(gt_pts) * 2,
        qualityLevel=0.01,
        minDistance=10,
        blockSize=7,
    )
    assert corners is not None, "goodFeaturesToTrack found no corners"

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
    corners_refined = cv2.cornerSubPix(img, corners, (11, 11), (-1, -1), criteria)

    gt_arr = np.array(gt_pts, dtype=np.float32)
    det_arr = corners_refined.reshape(-1, 2)

    errors: list[float] = []
    for gx, gy in gt_arr:
        dists = np.sqrt((det_arr[:, 0] - gx) ** 2 + (det_arr[:, 1] - gy) ** 2)
        errors.append(float(dists.min()))

    max_error = max(errors)
    mean_error = sum(errors) / len(errors)
    assert max_error < 0.1, (
        f"Max saddle-point error {max_error:.4f} px exceeds 0.1 px threshold "
        f"(mean={mean_error:.4f} px)"
    )


def test_aprilgrid_corner_square_symmetry():
    """AprilGrid corner squares must be symmetric (<=1 px) around intersections."""
    config = BoardConfig(
        type=BoardType.APRILGRID,
        rows=4,
        cols=5,
        marker_size=0.06,
        spacing_ratio=0.3,
        dictionary="tag36h11",
    )
    factory = TextureFactory(px_per_mm=10)
    img = factory.generate_board_texture(config)

    gt_pts = _grid_intersection_points(config, factory)
    assert len(gt_pts) == (config.rows - 1) * (config.cols - 1)

    for gx_f, gy_f in gt_pts:
        cx = round(gx_f + 0.5)
        cy = round(gy_f + 0.5)

        assert img[cy, cx] == 0, f"Pixel at intersection ({cx},{cy}) is {img[cy, cx]}, expected 0"

        left = cx
        while left > 0 and img[cy, left - 1] == 0:
            left -= 1
        right = cx
        while right < img.shape[1] - 1 and img[cy, right + 1] == 0:
            right += 1
        h_left = cx - left
        h_right = right - cx

        top = cy
        while top > 0 and img[top - 1, cx] == 0:
            top -= 1
        bottom = cy
        while bottom < img.shape[0] - 1 and img[bottom + 1, cx] == 0:
            bottom += 1
        v_top = cy - top
        v_bottom = bottom - cy

        # Even-sized squares on a discrete grid have at most 1 px asymmetry
        # because the slice [cx-half:cx+half] gives left=half, right=half-1.
        assert abs(h_left - h_right) <= 1, (
            f"Horizontal asymmetry at ({cx},{cy}): left={h_left}, right={h_right}"
        )
        assert abs(v_top - v_bottom) <= 1, (
            f"Vertical asymmetry at ({cx},{cy}): top={v_top}, bottom={v_bottom}"
        )
        assert h_left == v_top, f"Non-square corner at ({cx},{cy}): h={h_left}, v={v_top}"


def test_integer_aligned_grid_intersections():
    """Verify that grid intersections fall on exact pixel boundaries."""
    config = BoardConfig(
        type=BoardType.CHARUCO,
        rows=5,
        cols=7,
        square_size=0.05,
        marker_size=0.04,
        dictionary="DICT_4X4_50",
        quiet_zone_m=0.005,
    )
    factory = TextureFactory(px_per_mm=10)
    gm = factory.compute_grid_metrics(config)

    for r in range(config.rows + 1):
        coord = r * gm.square_px + gm.quiet_zone_px
        assert coord == int(coord), f"Row {r}: intersection at {coord} is not integer"
    for c in range(config.cols + 1):
        coord = c * gm.square_px + gm.quiet_zone_px
        assert coord == int(coord), f"Col {c}: intersection at {coord} is not integer"
