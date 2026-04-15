"""
Annotation and formatting utilities for render-tag.

Pure-Python implementations of bounding box calculations and reordering.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from render_tag.core.schema.base import KEYPOINT_SENTINEL, KeypointVisibility, is_sentinel_keypoint
from render_tag.generation.projection_math import (
    apply_distortion_by_model,
    quaternion_wxyz_to_matrix,
    validate_winding_order,
)


def _clip_polygon_near_plane(
    points: np.ndarray,
    z_near: float = 0.001,
) -> list[np.ndarray]:
    """Sutherland-Hodgman clip of a 3D polygon against the near plane Z = z_near."""
    clipped: list[np.ndarray] = []
    n = len(points)
    for i in range(n):
        p1, p2 = points[i], points[(i + 1) % n]
        p1_in, p2_in = p1[2] > z_near, p2[2] > z_near
        if p1_in and p2_in:
            clipped.append(p2)
        elif p1_in and not p2_in:
            t = (z_near - p1[2]) / (p2[2] - p1[2])
            clipped.append(p1 + t * (p2 - p1))
        elif not p1_in and p2_in:
            t = (z_near - p1[2]) / (p2[2] - p1[2])
            clipped.append(p1 + t * (p2 - p1))
            clipped.append(p2)
    return clipped


def compute_bbox(
    points: np.ndarray,
    detection: Any | None = None,
    distortion_coeffs: list[float] | None = None,
    distortion_model: str = "none",
) -> list[float]:
    """Compute [x, y, width, height] bounding box for a set of points.

    When distortion_coeffs is provided and non-zero, the Path A (3D reconstruction)
    branch applies the specified distortion model (brown_conrady or kannala_brandt)
    to the clipped polygon before final K-matrix projection, yielding a pixel-perfect
    bbox that accounts for curved tag edges under lens distortion.

    Args:
        points: (N, 2) array of coordinates.
        detection: Optional DetectionRecord with 3D pose, intrinsics, and size.
        distortion_coeffs: Optional distortion coefficients for the active model.

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

        clipped_polygon = _clip_polygon_near_plane(points_cam)
        if len(clipped_polygon) < 3:
            return [0.0, 0.0, 0.0, 0.0]

        clipped_polygon = np.array(clipped_polygon)

        # Project clipped polygon using Intrinsic Matrix K
        fx, fy = k_matrix[0, 0], k_matrix[1, 1]
        cx, cy = k_matrix[0, 2], k_matrix[1, 2]

        z = clipped_polygon[:, 2]
        x_norm = clipped_polygon[:, 0] / z
        y_norm = clipped_polygon[:, 1] / z

        x_norm, y_norm = apply_distortion_by_model(
            x_norm, y_norm, distortion_coeffs or [], distortion_model
        )

        x_proj = x_norm * fx + cx
        y_proj = y_norm * fy + cy

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


def _project_cam_point(
    p_cam: np.ndarray,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    dist_coeffs: list[float],
    dist_model: str,
) -> tuple[float, float]:
    """Project one camera-space point to distorted pixel coordinates."""
    x_n = p_cam[0] / p_cam[2]
    y_n = p_cam[1] / p_cam[2]
    xd, yd = apply_distortion_by_model(np.array([x_n]), np.array([y_n]), dist_coeffs, dist_model)
    return float(fx * xd[0] + cx), float(fy * yd[0] + cy)


def _adaptive_edge(
    p1: np.ndarray,
    p2: np.ndarray,
    proj1: tuple[float, float],
    proj2: tuple[float, float],
    project_fn: Any,
    max_error_px: float,
    depth: int,
    max_depth: int,
) -> list[tuple[float, float]]:
    """Recursively bisect edge p1→p2 in camera space until chord error < max_error_px.

    Returns projected points for the half-open interval (p1, p2] so that
    consecutive edges can be concatenated without duplicating shared vertices.
    """
    pmid = (p1 + p2) * 0.5
    proj_mid = project_fn(pmid)
    chord_x = (proj1[0] + proj2[0]) * 0.5
    chord_y = (proj1[1] + proj2[1]) * 0.5
    err_sq = (proj_mid[0] - chord_x) ** 2 + (proj_mid[1] - chord_y) ** 2
    if depth >= max_depth or err_sq <= max_error_px * max_error_px:
        return [proj2]
    left = _adaptive_edge(p1, pmid, proj1, proj_mid, project_fn, max_error_px, depth + 1, max_depth)
    right = _adaptive_edge(
        pmid, p2, proj_mid, proj2, project_fn, max_error_px, depth + 1, max_depth
    )
    return left + right


def compute_dense_distorted_polygon(
    detection: Any,
    distortion_coeffs: list[float],
    distortion_model: str,
    max_error_px: float = 0.1,
) -> list[tuple[float, float]] | None:
    """Generate a pixel-tight polygon by adaptively sampling tag edges in camera space.

    For fisheye (Kannala-Brandt) lenses, tag edges are curves in distorted pixel space.
    Each edge is recursively bisected in 3D camera space until the projected chord error
    is below ``max_error_px``, guaranteeing sub-pixel polygon accuracy regardless of
    tag size, distance, or distortion magnitude.

    Args:
        detection: DetectionRecord with position, rotation_quaternion, k_matrix, tag_size_mm.
        distortion_coeffs: Distortion coefficients for the active model.
        distortion_model: 'kannala_brandt' or 'brown_conrady'.
        max_error_px: Maximum allowed chord-to-arc error in pixels. Default 0.1px.

    Returns:
        List of (x, y) pixel coordinates forming the polygon, or None if pose
        information is unavailable (caller should fall back to the raw 4-corner polygon).
    """
    if not (
        detection is not None
        and getattr(detection, "position", None) is not None
        and getattr(detection, "rotation_quaternion", None) is not None
        and getattr(detection, "k_matrix", None) is not None
        and getattr(detection, "tag_size_mm", None) is not None
        and getattr(detection, "record_type", "") == "TAG"
    ):
        return None

    pos = np.array(detection.position)
    rot_mat = quaternion_wxyz_to_matrix(detection.rotation_quaternion)
    k_matrix = np.array(detection.k_matrix)
    half = detection.tag_size_mm / 1000.0 / 2.0
    fx, fy = float(k_matrix[0, 0]), float(k_matrix[1, 1])
    cx, cy = float(k_matrix[0, 2]), float(k_matrix[1, 2])

    # Center-Origin Convention: +X Right, +Y Down, +Z Into the plane.
    local_corners = np.array(
        [
            [-half, -half, 0.0],  # TL
            [half, -half, 0.0],  # TR
            [half, half, 0.0],  # BR
            [-half, half, 0.0],  # BL
        ]
    )
    points_cam = (rot_mat @ local_corners.T).T + pos

    clipped = _clip_polygon_near_plane(points_cam)
    if len(clipped) < 3:
        return None

    clipped_arr = np.array(clipped)
    m = len(clipped_arr)

    def project(p: np.ndarray) -> tuple[float, float]:
        return _project_cam_point(p, fx, fy, cx, cy, distortion_coeffs or [], distortion_model)

    # Build polygon by adaptive subdivision; each call returns (p1, p2] so vertices
    # are not duplicated at shared corners.
    result: list[tuple[float, float]] = [project(clipped_arr[0])]
    for i in range(m):
        p1 = clipped_arr[i]
        p2 = clipped_arr[(i + 1) % m]
        proj1 = project(p1)
        proj2 = project(p2)
        result.extend(_adaptive_edge(p1, p2, proj1, proj2, project, max_error_px, 0, max_depth=12))

    return result


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


def compute_eval_visibility(
    points: np.ndarray,
    width: int,
    height: int,
    margin_px: int = 0,
) -> np.ndarray:
    """Compute per-keypoint visibility booleans for COCO export with an edge margin.

    A point is True (v=2 / VISIBLE) only if it lies strictly inside the inner
    region [margin_px, W-margin_px) x [margin_px, H-margin_px).  Sentinel points
    and points outside the image boundary are False (v=0 or v=1).

    Delegates to ``compute_eval_visibility_ternary`` and compares against VISIBLE.

    Args:
        points: (N, 2) pixel coordinates.
        width: Image width in pixels.
        height: Image height in pixels.
        margin_px: Evaluation margin in pixels. 0 means no margin (full image is valid).

    Returns:
        Boolean array of length N.
    """
    ternary = compute_eval_visibility_ternary(points, width, height, margin_px)
    return ternary == KeypointVisibility.VISIBLE


def compute_eval_visibility_ternary(
    points: np.ndarray,
    width: int,
    height: int,
    margin_px: int = 0,
) -> np.ndarray:
    """Compute per-keypoint ternary visibility state (0/1/2) for rich_truth serialization.

    Unlike ``compute_eval_visibility`` (which returns booleans for COCO), this
    function returns the full ``KeypointVisibility`` integer:
      - ``OUT_OF_FRAME (0)``   — sentinel point (-1, -1)
      - ``MARGIN_TRUNCATED (1)`` — in image, inside eval_margin_px edge zone
      - ``VISIBLE (2)``        — inside the inner safe region

    Args:
        points: (N, 2) pixel coordinates.
        width: Image width in pixels.
        height: Image height in pixels.
        margin_px: Evaluation margin in pixels. 0 means no margin.

    Returns:
        Integer array of length N with values in {0, 1, 2}.
    """
    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    sentinel = (x == KEYPOINT_SENTINEL[0]) & (y == KEYPOINT_SENTINEL[1])

    # Default to MARGIN_TRUNCATED — covers out-of-image non-sentinel points too
    result = np.full(len(pts), KeypointVisibility.MARGIN_TRUNCATED, dtype=np.int8)
    result[sentinel] = KeypointVisibility.OUT_OF_FRAME
    in_inner = (
        (x >= margin_px) & (x < width - margin_px) & (y >= margin_px) & (y < height - margin_px)
    )
    result[in_inner & ~sentinel] = KeypointVisibility.VISIBLE
    return result


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
