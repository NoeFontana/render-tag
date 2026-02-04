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

    # Single point
    pts = np.array([[10, 10]])
    assert compute_bbox(pts) == [10.0, 10.0, 0.0, 0.0]


def test_normalize_corner_order_ccw_bl():
    # Input is already ccw_bl: BL, BR, TR, TL
    corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    ordered = normalize_corner_order(corners, target_order="ccw_bl")

    assert ordered[0] == (0.0, 0.0)
    assert ordered[1] == (1.0, 0.0)
    assert ordered[2] == (1.0, 1.0)
    assert ordered[3] == (0.0, 1.0)


def test_normalize_corner_order_cw_tl():
    # Input: BL, BR, TR, TL
    corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    # Target: CW from TL -> TL, TR, BR, BL
    ordered = normalize_corner_order(corners, target_order="cw_tl")

    assert ordered[0] == (0.0, 1.0)  # TL
    assert ordered[1] == (1.0, 1.0)  # TR
    assert ordered[2] == (1.0, 0.0)  # BR
    assert ordered[3] == (0.0, 0.0)  # BL


def test_verify_corner_order():
    # CCW ordered corners
    ccw = [(0, 0), (100, 0), (100, 100), (0, 100)]
    assert verify_corner_order(ccw, "ccw") is True
    assert verify_corner_order(ccw, "cw") is False

    # CW ordered corners (reversed)
    cw = [(0, 100), (100, 100), (100, 0), (0, 0)]
    assert verify_corner_order(cw, "cw") is True
    assert verify_corner_order(cw, "ccw") is False

    # Invalid
    assert verify_corner_order([(0, 0), (1, 1), (2, 2)], "ccw") is False
