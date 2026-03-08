"""
Annotation and formatting utilities for render-tag.

Pure-Python implementations of bounding box calculations and reordering.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from render_tag.generation.projection_math import quaternion_wxyz_to_matrix


def compute_bbox(points: np.ndarray, detection: Any | None = None) -> list[float]:
    """Compute [x, y, width, height] bounding box for a set of points.

    Args:
        points: (N, 2) array of coordinates.
        detection: Optional DetectionRecord with 3D pose, intrinsics, and size.

    Returns:
        [x_min, y_min, width, height].
        Returns [0,0,0,0] if insufficient valid points remain.
        Points with coordinates <= -999999 are considered invalid.
    """
    if len(points) == 0:
        return [0.0, 0.0, 0.0, 0.0]

    # Reconstruct 3D corners and clip against near plane if pose information is available
    if (
        detection is not None
        and getattr(detection, "position", None) is not None
        and getattr(detection, "rotation_quaternion", None) is not None
        and getattr(detection, "k_matrix", None) is not None
        and getattr(detection, "tag_size_mm", None) is not None
        and getattr(detection, "record_type", "") == "TAG"
    ):
        pos = np.array(detection.position)
        rot_quat = detection.rotation_quaternion  # [w, x, y, z]
        k_matrix = np.array(detection.k_matrix)
        marker_size_m = detection.tag_size_mm / 1000.0

        m = marker_size_m / 2.0
        # Tag local corners: TL, TR, BR, BL
        local_corners = np.array([[-m, m, 0.0], [m, m, 0.0], [m, -m, 0.0], [-m, -m, 0.0]])

        rot_mat = quaternion_wxyz_to_matrix(rot_quat)
        points_cam = (rot_mat @ local_corners.T).T + pos

        # Sutherland-Hodgman clipping against near plane (Z = 0.001)
        z_near = 0.001
        clipped_polygon = []

        for i in range(len(points_cam)):
            p1 = points_cam[i]
            p2 = points_cam[(i + 1) % len(points_cam)]

            p1_inside = p1[2] > z_near
            p2_inside = p2[2] > z_near

            if p1_inside and p2_inside:
                clipped_polygon.append(p2)
            elif p1_inside and not p2_inside:
                t = (z_near - p1[2]) / (p2[2] - p1[2])
                clipped_polygon.append(p1 + t * (p2 - p1))
            elif not p1_inside and p2_inside:
                t = (z_near - p1[2]) / (p2[2] - p1[2])
                clipped_polygon.append(p1 + t * (p2 - p1))
                clipped_polygon.append(p2)

        if len(clipped_polygon) < 3:
            return [0.0, 0.0, 0.0, 0.0]

        clipped_polygon = np.array(clipped_polygon)

        # Project clipped polygon using Intrinsic Matrix K
        fx, fy = k_matrix[0, 0], k_matrix[1, 1]
        cx, cy = k_matrix[0, 2], k_matrix[1, 2]

        z = clipped_polygon[:, 2]
        x_proj = (clipped_polygon[:, 0] * fx / z) + cx
        y_proj = (clipped_polygon[:, 1] * fy / z) + cy

        x_min, x_max = np.min(x_proj), np.max(x_proj)
        y_min, y_max = np.min(y_proj), np.max(y_proj)

        return [float(x_min), float(y_min), float(x_max - x_min), float(y_max - y_min)]

    # Fallback to 2D bounding box if no 3D information is provided
    # Filter out invalid points (behind camera marker is -1e6)
    mask = np.all(points > -999999.0, axis=1)
    valid_points = points[mask]

    if len(valid_points) < 2:
        return [0.0, 0.0, 0.0, 0.0]

    x_min, y_min = np.min(valid_points, axis=0)
    x_max, y_max = np.max(valid_points, axis=0)

    return [float(x_min), float(y_min), float(x_max - x_min), float(y_max - y_min)]


def normalize_corner_order(
    corners: np.ndarray | list[tuple[float, float]],
    target_order: str = "cw_tl",
) -> list[tuple[float, float]]:
    """Normalize 4 tag corners to a standard order.

    Target Orders:
    - cw_tl: Top-Left (0), Top-Right (1), Bottom-Right (2), Bottom-Left (3) [Standard/OpenCV]
    - ccw_bl: Bottom-Left (0), Bottom-Right (1), Top-Right (2), Top-Left (3)

    Args:
        corners: (4, 2) corner coordinates.
        target_order: Desired output order.

    Returns:
        List of 4 (x, y) tuples.
    """
    corners = np.asarray(corners)
    assert corners.ndim == 2, "Corners must be a 2D array."
    assert corners.shape[1] == 2, "Corners must have 2 columns (x, y)."
    if corners.shape != (4, 2):
        # If not exactly 4 corners, return as-is after converting to tuples
        return [(float(pt[0]), float(pt[1])) for pt in corners]
    assert len(corners) == 4

    # Current logic in writers.py and backend now assumes input is CW from TL
    # TL, TR, BR, BL
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]

    if target_order == "cw_tl":
        ordered = [tl, tr, br, bl]
    elif target_order == "ccw_bl":
        # BL, BR, TR, TL
        ordered = [bl, br, tr, tl]
    else:
        # If target_order is unknown, return original corners as tuples
        ordered = [(float(p[0]), float(p[1])) for p in corners]

    return [(float(p[0]), float(p[1])) for p in ordered]


def verify_corner_order(
    corners: np.ndarray | list[tuple[float, float]],
    expected_order: str = "ccw",
) -> bool:
    """Verify that corners are in the expected winding order.

    Args:
        corners: (4, 2) corner coordinates.
        expected_order: "ccw" (positive area) or "cw" (negative area).

    Returns:
        True if the winding order matches.
    """
    corners = np.asarray(corners)
    if len(corners) != 4:
        return False

    # We need signed area for winding order
    x = corners[:, 0]
    y = corners[:, 1]
    signed_area = 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    if expected_order == "ccw":
        return bool(signed_area < 0)
    else:  # cw
        return bool(signed_area > 0)


def format_coco_keypoints(
    points: np.ndarray,
    visibility: np.ndarray | list[bool] | None = None,
) -> list[float | int]:
    """Format 2D points into COCO keypoints list [x1, y1, v1, x2, y2, v2, ...].

    Visibility flags (v):
    0: not labeled (in which case x=y=0)
    1: labeled but not visible
    2: labeled and visible

    Args:
        points: (N, 2) array of coordinates.
        visibility: (N,) boolean array/list. If True, v=2. If False, v=1.
                    If None, assumes all visible (v=2).

    Returns:
        Flattened list of keypoints.
    """
    if len(points) == 0:
        return []

    points = np.asarray(points)

    visibility = np.ones(len(points), dtype=bool) if visibility is None else np.asarray(visibility)

    keypoints = []
    for (x, y), is_visible in zip(points, visibility, strict=False):
        v = 2 if is_visible else 1
        keypoints.extend([float(x), float(y), v])

    return keypoints
