"""
Zero-Render Math Verifier for render-tag.

This module contains pure-Python tests using numpy only to verify corner
projection logic and coordinate systems WITHOUT rendering a single pixel.

Benefit: Runs in ~0.01s vs 10s with Blender. Agents can iterate on coordinate
logic instantly.
"""

import math

import numpy as np


# ============================================================================
# Pure Math Projection Utilities (no Blender dependency)
# ============================================================================


def make_k_matrix(fx: float, fy: float, cx: float, cy: float) -> np.ndarray:
    """Create a 3x3 camera intrinsic matrix K.
    
    Args:
        fx: Focal length in x (pixels)
        fy: Focal length in y (pixels)
        cx: Principal point x (pixels)
        cy: Principal point y (pixels)
        
    Returns:
        3x3 intrinsic matrix K
    """
    return np.array([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0],
    ])


def k_from_fov(resolution: tuple[int, int], fov_degrees: float) -> np.ndarray:
    """Compute camera intrinsic matrix K from resolution and FOV.
    
    Args:
        resolution: (width, height) in pixels
        fov_degrees: Horizontal field of view in degrees
        
    Returns:
        3x3 intrinsic matrix K
    """
    width, height = resolution
    fx = fy = width / (2.0 * math.tan(math.radians(fov_degrees / 2.0)))
    cx, cy = width / 2.0, height / 2.0
    return make_k_matrix(fx, fy, cx, cy)


def make_extrinsics(
    camera_position: np.ndarray,
    look_at: np.ndarray,
    up: np.ndarray = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Create camera extrinsics (R, t) from position and look-at point.
    
    Uses OpenCV camera convention: Z forward, Y down, X right.
    
    Args:
        camera_position: 3D camera location in world space
        look_at: 3D point the camera is looking at
        up: World up vector (default: +Z)
        
    Returns:
        Tuple of (R, t) where R is 3x3 rotation and t is 3x1 translation
    """
    if up is None:
        up = np.array([0.0, 0.0, 1.0])
    
    # Forward vector (from camera to target)
    forward = look_at - camera_position
    forward = forward / np.linalg.norm(forward)
    
    # Right vector - handle degenerate case when forward is parallel to up
    right = np.cross(forward, up)
    right_norm = np.linalg.norm(right)
    
    if right_norm < 1e-6:
        # Forward is parallel to up, use a different up vector
        alt_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, alt_up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6:
            # Still degenerate, use X axis
            alt_up = np.array([1.0, 0.0, 0.0])
            right = np.cross(forward, alt_up)
            right_norm = np.linalg.norm(right)
    
    right = right / right_norm
    
    # Recompute up to ensure orthogonality
    cam_up = np.cross(right, forward)
    cam_up = cam_up / np.linalg.norm(cam_up)
    
    # Rotation matrix (world to camera)
    # OpenCV convention: Z forward, Y down, X right
    # So: X=right, Y=-cam_up (down), Z=forward
    R = np.array([
        right,
        -cam_up,
        forward,
    ])
    
    # Translation: negative of camera position rotated into camera frame
    t = -R @ camera_position
    
    return R, t.reshape(3, 1)


def project_point_3d_to_2d(
    point_3d: np.ndarray,
    K: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
) -> np.ndarray:
    """Project a 3D world point to 2D image coordinates.
    
    Uses the standard pinhole camera model: p_2d = K @ [R|t] @ P_3d
    
    Args:
        point_3d: 3D point in world coordinates (3,)
        K: 3x3 intrinsic matrix
        R: 3x3 rotation matrix (world to camera)
        t: 3x1 translation vector
        
    Returns:
        2D point in image coordinates (x, y)
    """
    # Transform to camera coordinates
    p_cam = R @ point_3d.reshape(3, 1) + t
    
    # Check if point is behind camera
    if p_cam[2, 0] <= 0:
        return np.array([np.nan, np.nan])
    
    # Project to image plane
    p_img_homogeneous = K @ p_cam
    
    # Normalize
    x = p_img_homogeneous[0, 0] / p_img_homogeneous[2, 0]
    y = p_img_homogeneous[1, 0] / p_img_homogeneous[2, 0]
    
    return np.array([x, y])


def project_corners(
    corners_3d: list[np.ndarray],
    K: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
) -> list[tuple[float, float]]:
    """Project multiple 3D corners to 2D image coordinates.
    
    Args:
        corners_3d: List of 4 corner positions in world space
        K: 3x3 intrinsic matrix
        R: 3x3 rotation matrix
        t: 3x1 translation vector
        
    Returns:
        List of 4 (x, y) tuples in image coordinates
    """
    corners_2d = []
    for corner in corners_3d:
        p2d = project_point_3d_to_2d(corner, K, R, t)
        corners_2d.append((float(p2d[0]), float(p2d[1])))
    return corners_2d


def compute_tag_corners_3d(
    center: np.ndarray,
    size: float,
    normal: np.ndarray = np.array([0, 0, 1]),
) -> list[np.ndarray]:
    """Compute 3D corner positions for a square tag.
    
    Corner order: BL (bottom-left), BR, TR, TL (counter-clockwise from BL).
    
    Args:
        center: 3D center position of the tag
        size: Side length of the tag
        normal: Normal vector of the tag plane (default: +Z up)
        
    Returns:
        List of 4 corner positions in 3D
    """
    half = size / 2.0
    
    # Default: tag lies in XY plane with Z as normal
    # Corners in CCW order: BL, BR, TR, TL
    corners = [
        center + np.array([-half, -half, 0]),  # BL
        center + np.array([+half, -half, 0]),  # BR
        center + np.array([+half, +half, 0]),  # TR
        center + np.array([-half, +half, 0]),  # TL
    ]
    
    return corners


def compute_polygon_area(corners_2d: list[tuple[float, float]]) -> float:
    """Compute polygon area using the Shoelace formula.
    
    Args:
        corners_2d: List of (x, y) corner coordinates
        
    Returns:
        Area in square pixels
    """
    n = len(corners_2d)
    if n < 3:
        return 0.0
    
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += corners_2d[i][0] * corners_2d[j][1]
        area -= corners_2d[j][0] * corners_2d[i][1]
    
    return abs(area) / 2.0


# ============================================================================
# Tests
# ============================================================================


class TestProjectionBasics:
    """Test basic 3D to 2D projection math."""
    
    def test_simple_projection_forward_facing(self) -> None:
        """Tag directly in front of camera should project to center."""
        # Setup: 640x480 camera with 60° FOV
        K = k_from_fov((640, 480), 60.0)
        
        # Camera at (0, 0, 1) looking at origin
        cam_pos = np.array([0.0, 0.0, 1.0])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        # Point at origin should project to image center
        point = np.array([0.0, 0.0, 0.0])
        p2d = project_point_3d_to_2d(point, K, R, t)
        
        # Should be near center (320, 240) with some tolerance
        assert abs(p2d[0] - 320) < 1.0, f"Expected x≈320, got {p2d[0]}"
        assert abs(p2d[1] - 240) < 1.0, f"Expected y≈240, got {p2d[1]}"
    
    def test_projection_off_axis(self) -> None:
        """Tag at angle should show perspective foreshortening."""
        K = k_from_fov((640, 480), 60.0)
        
        # Camera at (0, 0, 1) looking at origin
        cam_pos = np.array([0.0, 0.0, 1.0])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        # Point to the right of center
        point_right = np.array([0.5, 0.0, 0.0])
        p2d_right = project_point_3d_to_2d(point_right, K, R, t)
        
        # Should be to the right of center (x > 320)
        assert p2d_right[0] > 320, f"Expected x>320, got {p2d_right[0]}"
        
        # Point below center (in world Y)
        point_below = np.array([0.0, -0.5, 0.0])
        p2d_below = project_point_3d_to_2d(point_below, K, R, t)
        
        # In OpenCV convention, Y increases downward in image
        # World -Y maps to image +Y (below center)
        assert p2d_below[1] > 240, f"Expected y>240, got {p2d_below[1]}"
    
    def test_point_behind_camera_returns_nan(self) -> None:
        """Points behind camera should return NaN."""
        K = k_from_fov((640, 480), 60.0)
        
        cam_pos = np.array([0.0, 0.0, 1.0])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        # Point behind camera
        point_behind = np.array([0.0, 0.0, 2.0])
        p2d = project_point_3d_to_2d(point_behind, K, R, t)
        
        assert np.isnan(p2d[0]) and np.isnan(p2d[1])


class TestCornerProjection:
    """Test tag corner projection and ordering."""
    
    def test_corner_order_consistency(self) -> None:
        """Verify BL→BR→TR→TL ordering is maintained in projection."""
        K = k_from_fov((640, 480), 60.0)
        
        # Camera above and in front of tag
        cam_pos = np.array([0.0, -0.5, 1.0])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        # Tag at origin, 0.1m size
        corners_3d = compute_tag_corners_3d(np.array([0.0, 0.0, 0.0]), size=0.1)
        corners_2d = project_corners(corners_3d, K, R, t)
        
        # Verify we got 4 corners
        assert len(corners_2d) == 4
        
        # BL should be left of BR
        bl, br, tr, tl = corners_2d
        assert bl[0] < br[0], "BL should be left of BR"
        
        # BR should be below TR (in image coords, Y increases downward)
        assert br[1] > tr[1], "BR should be below TR (higher Y in image)"
        
        # TL should be left of TR
        assert tl[0] < tr[0], "TL should be left of TR"
    
    def test_projected_tag_is_quadrilateral(self) -> None:
        """Projected corners should form a valid quadrilateral."""
        K = k_from_fov((640, 480), 60.0)
        
        cam_pos = np.array([0.0, -0.3, 0.8])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        corners_3d = compute_tag_corners_3d(np.array([0.0, 0.0, 0.0]), size=0.1)
        corners_2d = project_corners(corners_3d, K, R, t)
        
        # All corners should have valid coordinates
        for i, (x, y) in enumerate(corners_2d):
            assert not np.isnan(x), f"Corner {i} has NaN x"
            assert not np.isnan(y), f"Corner {i} has NaN y"
        
        # Area should be positive
        area = compute_polygon_area(corners_2d)
        assert area > 0, f"Quad area should be positive, got {area}"


class TestAreaCalculation:
    """Test area computation using Shoelace formula."""
    
    def test_tag_area_shoelace_unit_square(self) -> None:
        """Unit square should have area 1."""
        corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
        area = compute_polygon_area(corners)
        assert abs(area - 1.0) < 1e-9
    
    def test_tag_area_shoelace_scaled(self) -> None:
        """10x10 square should have area 100."""
        corners = [(0, 0), (10, 0), (10, 10), (0, 10)]
        area = compute_polygon_area(corners)
        assert abs(area - 100.0) < 1e-9
    
    def test_tag_area_shoelace_triangle(self) -> None:
        """Triangle with base 4, height 3 should have area 6."""
        # Right triangle: (0,0), (4,0), (0,3)
        corners = [(0, 0), (4, 0), (0, 3)]
        area = compute_polygon_area(corners)
        assert abs(area - 6.0) < 1e-9
    
    def test_area_matches_projection_size(self) -> None:
        """Larger tags closer to camera should have larger area."""
        K = k_from_fov((640, 480), 60.0)
        
        cam_pos = np.array([0.0, 0.0, 1.0])
        look_at = np.array([0.0, 0.0, 0.0])
        R, t = make_extrinsics(cam_pos, look_at)
        
        # Small tag
        corners_small = compute_tag_corners_3d(np.array([0.0, 0.0, 0.0]), size=0.05)
        corners_2d_small = project_corners(corners_small, K, R, t)
        area_small = compute_polygon_area(corners_2d_small)
        
        # Large tag (same distance)
        corners_large = compute_tag_corners_3d(np.array([0.0, 0.0, 0.0]), size=0.1)
        corners_2d_large = project_corners(corners_large, K, R, t)
        area_large = compute_polygon_area(corners_2d_large)
        
        # Large tag should have ~4x the area (2x side length)
        ratio = area_large / area_small
        assert 3.5 < ratio < 4.5, f"Expected area ratio ~4, got {ratio}"


class TestIntrinsicsFromFOV:
    """Test camera intrinsics computation from FOV."""
    
    def test_k_from_fov_principal_point(self) -> None:
        """Principal point should be at image center."""
        K = k_from_fov((640, 480), 60.0)
        
        cx = K[0, 2]
        cy = K[1, 2]
        
        assert abs(cx - 320.0) < 1e-9, f"cx should be 320, got {cx}"
        assert abs(cy - 240.0) < 1e-9, f"cy should be 240, got {cy}"
    
    def test_k_from_fov_focal_length(self) -> None:
        """Focal length should match FOV geometry."""
        width = 640
        fov = 60.0
        K = k_from_fov((width, 480), fov)
        
        fx = K[0, 0]
        expected_fx = width / (2.0 * math.tan(math.radians(fov / 2.0)))
        
        assert abs(fx - expected_fx) < 1e-9
    
    def test_wider_fov_means_smaller_focal_length(self) -> None:
        """Wider FOV should produce smaller focal length."""
        K_60 = k_from_fov((640, 480), 60.0)
        K_90 = k_from_fov((640, 480), 90.0)
        
        fx_60 = K_60[0, 0]
        fx_90 = K_90[0, 0]
        
        assert fx_90 < fx_60, "90° FOV should have smaller focal length than 60°"
