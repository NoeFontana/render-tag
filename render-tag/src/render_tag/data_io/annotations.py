"""
Annotation and formatting utilities for render-tag.

Pure-Python implementations of bounding box calculations and reordering.
"""

from __future__ import annotations

import numpy as np


def compute_bbox(points: np.ndarray) -> list[float]:
    """Compute [x, y, width, height] bounding box for a set of points.

    Args:
        points: (N, 2) array of coordinates.

    Returns:
        [x_min, y_min, width, height]
    """
    if len(points) == 0:
        return [0.0, 0.0, 0.0, 0.0]

    x_min, y_min = np.min(points, axis=0)
    x_max, y_max = np.max(points, axis=0)

    return [float(x_min), float(y_min), float(x_max - x_min), float(y_max - y_min)]


def normalize_corner_order(
    corners: np.ndarray | list[tuple[float, float]],
    target_order: str = "ccw_bl",
) -> list[tuple[float, float]]:
    """Normalize 4 tag corners to a standard order.

    Target Orders:
    - ccw_bl: Bottom-Left (0), Bottom-Right (1), Top-Right (2), Top-Left (3) [Locus/Standard]
    - cw_tl: Top-Left (0), Top-Right (1), Bottom-Right (2), Bottom-Left (3) [COCO/OpenCV]

    Args:
        corners: (4, 2) corner coordinates.
        target_order: Desired output order.

    Returns:
        List of 4 (x, y) tuples.
    """
    corners = np.asarray(corners)
    if corners.shape != (4, 2):
        return [tuple(float(c) for c in pt) for pt in corners]

    # Current logic in writers.py assumes input is CCW from BL
    # BL, BR, TR, TL
    bl, br, tr, tl = corners[0], corners[1], corners[2], corners[3]

    if target_order == "cw_tl":
        # TL, TR, BR, BL
        ordered = [tl, tr, br, bl]
    elif target_order == "ccw_bl":
        ordered = [bl, br, tr, tl]
    else:
        ordered = list(corners)

    return [(float(p[0]), float(p[1])) for p in ordered]
