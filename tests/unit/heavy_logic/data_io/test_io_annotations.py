"""
Unit tests for annotation_utils module.
"""

from __future__ import annotations

import numpy as np

from render_tag.data_io.annotations import (
    compute_bbox,
    normalize_corner_order,
    verify_corner_order,
)


def test_compute_bbox():
    # Standard square
    pts = np.array([[10, 20], [30, 20], [30, 50], [10, 50]])
    bbox = compute_bbox(pts)
    # Expected: [x_min, y_min, w, h] = [10, 20, 20, 30]
    assert bbox == [10.0, 20.0, 20.0, 30.0]

    # Single point (now returns zero box per strict filtering requirement)
    pts = np.array([[10, 10]])
    assert compute_bbox(pts) == [0.0, 0.0, 0.0, 0.0]


def test_normalize_corner_order_default():
    # normalize_corner_order is a pass-through: it returns corners unchanged.
    corners_ordered = np.array([[0, 1], [1, 1], [1, 0], [0, 0]])
    ordered = normalize_corner_order(corners_ordered)

    assert ordered[0] == (0.0, 1.0)
    assert ordered[1] == (1.0, 1.0)
    assert ordered[2] == (1.0, 0.0)
    assert ordered[3] == (0.0, 0.0)


def test_normalize_corner_order_ccw_bl():
    # normalize_corner_order is a pass-through regardless of target_order.
    # The 3D asset contract guarantees corners are already CW from TL; no
    # image-space reordering is permitted.
    corners = np.array([[0, 1], [1, 1], [1, 0], [0, 0]])
    ordered = normalize_corner_order(corners)

    assert ordered[0] == (0.0, 1.0)
    assert ordered[1] == (1.0, 1.0)
    assert ordered[2] == (1.0, 0.0)
    assert ordered[3] == (0.0, 0.0)


def test_normalize_corner_order_cw_tl():
    # normalize_corner_order is a pass-through regardless of target_order.
    corners = np.array([[0, 1], [1, 1], [1, 0], [0, 0]])
    ordered = normalize_corner_order(corners)

    assert ordered[0] == (0.0, 1.0)
    assert ordered[1] == (1.0, 1.0)
    assert ordered[2] == (1.0, 0.0)
    assert ordered[3] == (0.0, 0.0)


def test_verify_corner_order():
    # In Y-down (OpenCV):
    # (0,0) -> (100,0) -> (100,100) -> (0,100) is CW (Positive Area)
    # Area = 0.5 * |(0*0 + 100*100 + 100*100 + 0*0) - (0*100 + 0*100 + 100*0 + 100*0)| = 10000
    cw = [(0, 0), (100, 0), (100, 100), (0, 100)]
    assert verify_corner_order(cw, "cw") is True
    assert verify_corner_order(cw, "ccw") is False

    # Reversed: CCW
    ccw = [(0, 100), (100, 100), (100, 0), (0, 0)]
    assert verify_corner_order(ccw, "ccw") is True
    assert verify_corner_order(ccw, "cw") is False

    # Invalid
    assert verify_corner_order([(0, 0), (1, 1), (2, 2)], "ccw") is False
