"""
Annotation and formatting utilities for render-tag.

Pure-Python implementations of bounding box calculations and reordering.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from render_tag.core.schema.base import is_sentinel_keypoint
from render_tag.generation.projection_math import (
    quaternion_wxyz_to_matrix,
    validate_winding_order,
)


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

        # Center-Origin Convention: Pose is anchored at the geometric center.
        # +X is Right, +Y is Down, +Z is Into the plane.
        half = marker_size_m / 2.0
        local_corners = np.array(
            [
                [-half, -half, 0.0],  # TL
                [half, -half, 0.0],  # TR
                [half, half, 0.0],  # BR
                [-half, half, 0.0],  # BL
            ]
        )

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
) -> list[tuple[float, float]]:
    """Convert corners to a list of (x, y) float tuples.

    The pipeline MUST NOT perform any image-space sorting of corners. Index 0 is
    always Top-Left and the winding is always Clockwise, as enforced by
    backend.projection. This function is a serialization helper only.

    Args:
        corners: (N, 2) corner coordinates.

    Returns:
        List of (x, y) tuples in the original order.
    """
    corners = np.asarray(corners)
    return [(float(pt[0]), float(pt[1])) for pt in corners]


def verify_corner_order(
    corners: np.ndarray | list[tuple[float, float]],
    expected_order: str = "cw",
) -> bool:
    """Verify that corners are in the expected winding order.

    Delegates to the single source of truth: ``validate_winding_order`` from
    ``render_tag.generation.projection_math``.  In a Y-down coordinate system
    (OpenCV/image space), Clockwise polygons have a positive signed area.

    Args:
        corners: (4, 2) corner coordinates.
        expected_order: "cw" (positive area, default) or "ccw" (negative area).

    Returns:
        True if the winding order matches.
    """
    corners = np.asarray(corners)
    if len(corners) != 4:
        return False

    if expected_order == "cw":
        return validate_winding_order(corners)
    else:  # ccw
        return not validate_winding_order(corners)


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
        visibility: (N,) boolean array/list. If True, v=2. If False and the
                    point is the sentinel (-1, -1), v=0 with zeroed coords.
                    If False otherwise, v=1. If None, assumes all visible (v=2).

    Returns:
        Flattened list of keypoints.
    """
    if len(points) == 0:
        return []

    points = np.asarray(points)

    visibility = np.ones(len(points), dtype=bool) if visibility is None else np.asarray(visibility)

    keypoints = []
    for (x, y), is_visible in zip(points, visibility, strict=False):
        if is_visible:
            keypoints.extend([float(x), float(y), 2])
        elif is_sentinel_keypoint(float(x), float(y)):
            keypoints.extend([0.0, 0.0, 0])  # COCO v=0: not labeled
        else:
            keypoints.extend([float(x), float(y), 1])

    return keypoints
