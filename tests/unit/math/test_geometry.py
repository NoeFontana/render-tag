from __future__ import annotations

import math

import numpy as np
import pytest

"""
Advanced unit tests for board geometry, focusing on malformed specs and failures.
"""

from render_tag.generation.board import (
    BoardLayout,
    BoardPosition,
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
    validate_aprilgrid_filling,
    validate_board_dimensions,
    validate_board_is_centered,
    validate_board_plausibility,
    validate_charuco_tag_filling,
    validate_charuco_white_border,
    validate_marker_fits_in_square,
    validate_no_overlaps,
)
from render_tag.generation.camera import sample_camera_pose, validate_camera_pose
from render_tag.generation.math import (
    compute_polygon_area,
    look_at_rotation,
    make_transformation_matrix,
    rotation_matrix_from_vectors,
)
from render_tag.generation.projection_math import (
    calculate_angle_of_incidence,
    get_opencv_camera_matrix,
    get_world_normal,
)
from render_tag.generation.visibility import (
    is_facing_camera,
    project_points,
    validate_visibility_metrics,
)

# ============================================================================


def test_invalid_marker_fits():
    # Marker larger than square
    spec = BoardSpec(rows=2, cols=2, square_size=0.1, marker_margin=-0.01)
    # marker_size = 0.1 - 2*(-0.01) = 0.12 > 0.1
    is_valid, msg = validate_marker_fits_in_square(spec)
    assert not is_valid
    assert "marker_margin" in msg or "Marker size" in msg

    # Zero/Negative marker size
    spec = BoardSpec(rows=2, cols=2, square_size=0.1, marker_margin=0.06)
    # marker_size = 0.1 - 0.12 = -0.02
    is_valid, msg = validate_marker_fits_in_square(spec)
    assert not is_valid
    assert "positive" in msg


def test_board_dimension_validation_failure():
    spec = BoardSpec(rows=4, cols=4, square_size=0.1)
    layout = compute_charuco_layout(spec)

    # Manually tamper with spec to make it inconsistent with layout
    layout.spec = BoardSpec(rows=4, cols=4, square_size=0.2)

    is_valid, msg = validate_board_dimensions(layout)
    assert not is_valid
    assert "width" in msg or "height" in msg


def test_board_centering_validation_failure():
    spec = BoardSpec(rows=4, cols=4, square_size=0.1)
    layout = compute_charuco_layout(spec, center=(0, 0, 0))

    # Tamper with center
    layout.center = BoardPosition(1.0, 1.0, 0.0)

    is_valid, msg = validate_board_is_centered(layout)
    assert not is_valid
    assert "Center" in msg


def test_empty_layout_validation():
    spec = BoardSpec(rows=0, cols=0, square_size=0.1)
    layout = BoardLayout(spec=spec)

    is_valid, msg = validate_board_is_centered(layout)
    assert not is_valid
    assert "No squares" in msg

    is_valid, msg = validate_board_dimensions(layout)
    assert not is_valid
    assert "No squares" in msg


"""
Tests for Board Geometry - Pure Python validation of board layouts.

These tests verify physical plausibility of calibration boards:
- White border on edges
- Tags fill all available positions (no gaps)
- Geometry invariants (centering, dimensions, no overlaps)

All tests run WITHOUT Blender.
"""

# ============================================================================
# BoardSpec Tests
# ============================================================================


class TestBoardSpec:
    """Test BoardSpec computed properties."""

    def test_board_dimensions(self) -> None:
        """Board dimensions = rows * cols * square_size."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)

        assert spec.board_width == 8 * 0.05  # cols * size
        assert spec.board_height == 6 * 0.05  # rows * size

    def test_marker_size_with_margin(self) -> None:
        """Marker size accounts for margin on both sides."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.10, marker_margin=0.01)

        # marker_size = square_size - 2 * margin
        assert spec.marker_size == 0.10 - 2 * 0.01
        assert spec.marker_size == 0.08

    def test_total_squares(self) -> None:
        """Total squares = rows * cols."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05)

        assert spec.total_squares == 5 * 7

    def test_charuco_white_square_count(self) -> None:
        """ChArUco white squares = ceil(total/2)."""
        # Even total
        spec_even = BoardSpec(rows=6, cols=8, square_size=0.05)
        assert spec_even.white_square_count == 24  # 48/2

        # Odd total
        spec_odd = BoardSpec(rows=5, cols=7, square_size=0.05)
        assert spec_odd.white_square_count == 18  # (35+1)/2 = 18

    def test_expected_tag_count_charuco(self) -> None:
        """ChArUco tag count = white square count."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05, board_type=BoardType.CHARUCO)
        assert spec.expected_tag_count == spec.white_square_count

    def test_expected_tag_count_aprilgrid(self) -> None:
        """AprilGrid tag count = total squares."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05, board_type=BoardType.APRILGRID)
        assert spec.expected_tag_count == spec.total_squares

    def test_corner_count_aprilgrid(self) -> None:
        """Corner count = (rows+1) * (cols+1)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        assert spec.corner_count == 7 * 9  # (6+1) * (8+1) = 63


# ============================================================================
# ChArUco Layout Tests
# ============================================================================


class TestCharucoLayout:
    """Test ChArUco board layout generation."""

    def test_charuco_generates_correct_square_count(self) -> None:
        """Layout should have rows * cols squares."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 48

    def test_charuco_generates_correct_tag_count(self) -> None:
        """Layout should have white_square_count tags."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.tag_positions) == spec.white_square_count

    def test_charuco_alternating_pattern(self) -> None:
        """Tags only in (row+col) % 2 == 0 positions."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1)
        layout = compute_charuco_layout(spec)

        for sq in layout.squares:
            expected_white = (sq.row + sq.col) % 2 == 0
            assert sq.is_white == expected_white, f"Square ({sq.row},{sq.col}) has wrong color"
            assert sq.has_tag == expected_white, f"Square ({sq.row},{sq.col}) tag status wrong"

    def test_charuco_has_white_border(self) -> None:
        """All corner squares should have same color (consistent border)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_charuco_white_border(layout)
        assert is_valid, msg

    def test_charuco_maximizes_tags(self) -> None:
        """All white squares should have tags (no gaps)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_charuco_tag_ids_are_sequential(self) -> None:
        """Tag IDs should be 0, 1, 2, ... in order."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1)
        layout = compute_charuco_layout(spec)

        tag_ids = [sq.tag_id for sq in layout.squares if sq.has_tag]
        expected_ids = list(range(len(tag_ids)))

        assert tag_ids == expected_ids, f"Tag IDs {tag_ids} != expected {expected_ids}"


# ============================================================================
# AprilGrid Layout Tests
# ============================================================================


class TestAprilGridLayout:
    """Test AprilGrid board layout generation."""

    def test_aprilgrid_fills_all_cells(self) -> None:
        """Every cell should have a tag."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec)

        is_valid, msg = validate_aprilgrid_filling(layout)
        assert is_valid, msg

    def test_aprilgrid_tag_count(self) -> None:
        """Tag count should equal total cells."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec)

        assert len(layout.tag_positions) == 5 * 7

    def test_aprilgrid_corner_count(self) -> None:
        """Corner count should be (rows+1) * (cols+1)."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec)

        assert len(layout.corner_positions) == 6 * 8  # (5+1) * (7+1) = 48

    def test_aprilgrid_positions_form_regular_grid(self) -> None:
        """Tag positions should form a regular grid with uniform spacing."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec)

        # Check that horizontal spacing is uniform
        xs = sorted({p.x for p in layout.tag_positions})
        for i in range(1, len(xs)):
            spacing = xs[i] - xs[i - 1]
            assert abs(spacing - spec.square_size) < 1e-9, f"Irregular x spacing: {spacing}"

        # Check that vertical spacing is uniform
        ys = sorted({p.y for p in layout.tag_positions})
        for i in range(1, len(ys)):
            spacing = ys[i] - ys[i - 1]
            assert abs(spacing - spec.square_size) < 1e-9, f"Irregular y spacing: {spacing}"


# ============================================================================
# Geometry Invariant Tests
# ============================================================================


class TestGeometryInvariants:
    """Test geometry invariants for all board types."""

    def test_board_is_centered_charuco(self) -> None:
        """ChArUco board should be centered at requested center."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec, center=(1.0, 2.0, 0.5))

        is_valid, msg = validate_board_is_centered(layout)
        assert is_valid, msg

    def test_board_is_centered_aprilgrid(self) -> None:
        """AprilGrid board should be centered at requested center."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec, center=(-0.5, 0.5, 0.0))

        is_valid, msg = validate_board_is_centered(layout)
        assert is_valid, msg

    def test_board_dimensions_correct(self) -> None:
        """Board should have expected width/height."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_board_dimensions(layout)
        assert is_valid, msg

    def test_no_overlapping_tags(self) -> None:
        """Tags should not overlap each other."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.01)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_no_overlaps(layout)
        assert is_valid, msg

    def test_marker_fits_in_square_valid(self) -> None:
        """Marker should fit within square with margin."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.01)

        is_valid, msg = validate_marker_fits_in_square(spec)
        assert is_valid, msg

    def test_marker_fits_in_square_invalid(self) -> None:
        """Detect when marker doesn't fit (margin too large)."""
        # Margin is half the square size, so marker_size = 0
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.05)

        is_valid, _msg = validate_marker_fits_in_square(spec)
        # This should still pass since 0.1 - 2*0.05 = 0 which is not positive
        # Actually spec.marker_size = 0 which fails the "must be positive" check
        assert not is_valid


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_row_charuco(self) -> None:
        """Single row board should work."""
        spec = BoardSpec(rows=1, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 8
        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_single_column_charuco(self) -> None:
        """Single column board should work."""
        spec = BoardSpec(rows=6, cols=1, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 6
        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_minimal_2x2_charuco(self) -> None:
        """Minimal 2x2 board should work."""
        spec = BoardSpec(rows=2, cols=2, square_size=0.1)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 4
        assert len(layout.tag_positions) == 2  # 2 white squares

    def test_large_board(self) -> None:
        """Large board should work without issues."""
        spec = BoardSpec(rows=20, cols=20, square_size=0.02)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 400
        assert len(layout.tag_positions) == 200


# ============================================================================
# Full Validation Suite Tests
# ============================================================================


class TestFullValidation:
    """Test the complete validation suite."""

    def test_plausibility_all_pass_charuco(self) -> None:
        """All plausibility checks should pass for valid ChArUco."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05, marker_margin=0.005)
        layout = compute_charuco_layout(spec)

        results = validate_board_plausibility(layout)

        for check_name, is_valid, msg in results:
            assert is_valid, f"Check '{check_name}' failed: {msg}"

    def test_plausibility_all_pass_aprilgrid(self) -> None:
        """All plausibility checks should pass for valid AprilGrid."""
        spec = BoardSpec(
            rows=5,
            cols=7,
            square_size=0.05,
            marker_margin=0.005,
            board_type=BoardType.APRILGRID,
        )
        layout = compute_aprilgrid_layout(spec)

        results = validate_board_plausibility(layout)

        for check_name, is_valid, msg in results:
            assert is_valid, f"Check '{check_name}' failed: {msg}"


def test_sample_camera_pose_bounds():
    look_at = np.array([0, 0, 0])
    min_dist, max_dist = 1.0, 2.0
    min_elev, max_elev = 0.5, 0.8

    # Sample many times to check distributions
    for _ in range(100):
        pose = sample_camera_pose(
            look_at,
            min_distance=min_dist,
            max_distance=max_dist,
            min_elevation=min_elev,
            max_elevation=max_elev,
        )

        dist = np.linalg.norm(pose.location - look_at)
        assert min_dist <= dist <= max_dist

        # Elevation is z-component of unit vector from center
        unit_vec = (pose.location - look_at) / dist
        elev = unit_vec[2]
        assert min_elev - 1e-6 <= elev <= max_elev + 1e-6

        # Check that it's looking at the target
        # Local forward in Blender is -Z (3rd column of R)
        # So -pose.rotation_matrix[:, 2] should point towards look_at
        forward = -pose.rotation_matrix[:, 2]
        to_target = look_at - pose.location
        to_target /= np.linalg.norm(to_target)

        assert np.allclose(forward, to_target, atol=1e-5)


def test_validate_camera_pose():
    look_at = np.array([0, 0, 0])

    # Valid pose
    pose_ok = sample_camera_pose(look_at, distance=1.0, elevation=0.5)
    assert validate_camera_pose(pose_ok, look_at, min_distance=0.5, min_height=0.1) is True

    # Too close
    assert validate_camera_pose(pose_ok, look_at, min_distance=1.5) is False

    # Too low
    pose_low = sample_camera_pose(look_at, distance=1.0, elevation=0.01)  # Very low
    assert validate_camera_pose(pose_low, look_at, min_height=0.1) is False


def test_rotation_matrix_alignment_edge_cases():
    # Case 1: Already aligned
    v1 = np.array([1, 0, 0])
    v2 = np.array([1, 0, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R, np.eye(3))
    assert np.allclose(R @ v1, v2)

    # Case 2: Exact opposite (180 degrees) - X axis
    v1 = np.array([1, 0, 0])
    v2 = np.array([-1, 0, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    # Check it's an orthogonal matrix
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 3: Exact opposite (180 degrees) - Y axis
    v1 = np.array([0, 1, 0])
    v2 = np.array([0, -1, 0])
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 4: Random vectors
    v1 = np.array([1, 2, 3], dtype=float)
    v1 /= np.linalg.norm(v1)
    v2 = np.array([-4, 5, 1], dtype=float)
    v2 /= np.linalg.norm(v2)
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))

    # Case 5: Near opposite (testing epsilon)
    v1 = np.array([1, 0, 0], dtype=float)
    v2 = np.array([-1, 1e-11, 0], dtype=float)  # Just outside exact opposite branch
    v2 /= np.linalg.norm(v2)
    R = rotation_matrix_from_vectors(v1, v2)
    assert np.allclose(R @ v1, v2)
    assert np.allclose(R.T @ R, np.eye(3))


def test_look_at_rotation_degenerate():
    # Forward is [0, 0, 1], Up is [0, 0, 1] (Parallel)
    f = np.array([0, 0, 1])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)

    # Forward is Z axis in world
    # Camera -Z is world Z => cam_z = [0, 0, -1]
    assert np.allclose(R[:, 2], -f)
    # Resulting matrix should still be orthogonal
    assert np.allclose(R.T @ R, np.eye(3))

    # Forward is opposite to up
    f = np.array([0, 0, -1])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)
    assert np.allclose(R[:, 2], -f)
    assert np.allclose(R.T @ R, np.eye(3))


def test_look_at_rotation_axes():
    # Forward along X, Up along Z
    f = np.array([1, 0, 0])
    up = np.array([0, 0, 1])
    R = look_at_rotation(f, up)

    # cam_z = -f = [-1, 0, 0]
    # x_axis = up x cam_z = [0, 0, 1] x [-1, 0, 0] = [0, -1, 0]
    # y_axis = cam_z x x_axis = [-1, 0, 0] x [0, -1, 0] = [0, 0, 1]

    assert np.allclose(R[:, 0], [0, -1, 0])  # X
    assert np.allclose(R[:, 1], [0, 0, 1])  # Y
    assert np.allclose(R[:, 2], [-1, 0, 0])  # Z


def test_compute_polygon_area():
    # Unit square
    points = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    assert compute_polygon_area(points) == pytest.approx(1.0)

    # Triangle
    points = np.array([[0, 0], [2, 0], [0, 2]])
    assert compute_polygon_area(points) == pytest.approx(2.0)

    # Empty/Insufficient points
    assert compute_polygon_area(np.array([[0, 0]])) == 0.0


def test_make_transformation_matrix():
    translation = np.array([1, 2, 3])
    rotation = np.eye(3)
    mat = make_transformation_matrix(translation, rotation)

    assert mat.shape == (4, 4)
    assert np.allclose(mat[:3, :3], rotation)
    assert np.allclose(mat[:3, 3], translation)
    assert mat[3, 3] == 1.0


def test_look_at_rotation_forward():
    # Camera at (0, 0, 1) looking at (0, 0, 0)
    # Forward vector is (0, 0, -1)
    forward = np.array([0, 0, -1])
    R = look_at_rotation(forward)

    # Camera axes in world coordinates
    # cam_z = -f = (0, 0, 1)
    # world_up = (0, 0, 1) -> Degenerate case handled by look_at_rotation
    # It should still produce a valid rotation matrix (orthogonal)
    assert np.allclose(R.T @ R, np.eye(3))
    assert np.isclose(np.linalg.det(R), 1.0)


def test_look_at_rotation_alignment():
    # Pointing along X axis
    forward = np.array([1, 0, 0])
    R = look_at_rotation(forward)

    # cam_z = -f = (-1, 0, 0)
    # cam_x = up(0,0,1) x cam_z(-1,0,0) = (0, -1, 0)
    # cam_y = cam_z(-1,0,0) x cam_x(0,-1,0) = (0, 0, 1)

    expected_x = np.array([0, -1, 0])
    expected_y = np.array([0, 0, 1])
    expected_z = np.array([-1, 0, 0])

    assert np.allclose(R[:, 0], expected_x)
    assert np.allclose(R[:, 1], expected_y)
    assert np.allclose(R[:, 2], expected_z)


def test_camera_matrix_conversion():
    # Identity matrix (Camera at origin, looking at -Z, Up is Y)
    blender_cam_to_world = np.eye(4)

    opencv_mat = get_opencv_camera_matrix(blender_cam_to_world)

    # In OpenCV, camera looks at +Z
    # So if blender_cam is identity, its -Z axis is world -Z.
    # The conversion flips Y and Z.
    # OpenCV Forward (Z) should now be World -Z
    # OpenCV Down (Y) should now be World -Y

    expected = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    assert np.allclose(opencv_mat, expected)


def test_get_world_normal():
    # Rotate 90 degrees around X (Y becomes Z)
    theta = np.radians(90)
    c, s = np.cos(theta), np.sin(theta)
    rot_x = np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])

    # Local normal [0, 0, 1]
    world_n = get_world_normal(rot_x)
    # [0, 0, 1] rotated 90 deg around X should be [0, -1, 0]
    assert np.allclose(world_n, [0, -1, 0])


def test_angle_of_incidence_edge_cases():
    target_pos = np.array([0, 0, 0])
    target_normal = np.array([0, 0, 1])

    # 1. Directly above (0 degrees)
    cam_pos = np.array([0, 0, 10])
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 0.0)

    # 2. Grazing angle (90 degrees)
    cam_pos = np.array([10, 0, 0])
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 90.0)

    # 3. Behind the surface (180 degrees or > 90)
    cam_pos = np.array([0, 0, -10])
    assert calculate_angle_of_incidence(target_pos, target_normal, cam_pos) > 90.0
    assert np.allclose(calculate_angle_of_incidence(target_pos, target_normal, cam_pos), 180.0)


# ============================================================================

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
    return np.array(
        [
            [fx, 0.0, cx],
            [0.0, fy, cy],
            [0.0, 0.0, 1.0],
        ]
    )


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
    up: np.ndarray | None = None,
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
    R = np.array(
        [
            right,
            -cam_up,
            forward,
        ]
    )

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
        (4, 2) array of corner coordinates
    """
    corners_2d = []
    for corner in corners_3d:
        p2d = project_point_3d_to_2d(corner, K, R, t)
        corners_2d.append([float(p2d[0]), float(p2d[1])])
    return np.array(corners_2d)


def compute_tag_corners_3d(
    center: np.ndarray,
    size: float,
    normal: np.ndarray | None = None,
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
    if normal is None:
        normal = np.array([0, 0, 1])
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
        corners = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
        area = compute_polygon_area(corners)
        assert abs(area - 1.0) < 1e-9

    def test_tag_area_shoelace_scaled(self) -> None:
        """10x10 square should have area 100."""
        corners = np.array([[0, 0], [10, 0], [10, 10], [0, 10]])
        area = compute_polygon_area(corners)
        assert abs(area - 100.0) < 1e-9

    def test_tag_area_shoelace_triangle(self) -> None:
        """Triangle with base 4, height 3 should have area 6."""
        # Right triangle: (0,0), (4,0), (0,3)
        corners = np.array([[0, 0], [4, 0], [0, 3]])
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


"""
Unit tests for visibility_geometry module.
"""


# ============================================================================


def test_is_facing_camera():
    tag_pos = np.array([0, 0, 0])
    tag_normal = np.array([0, 0, 1])  # Facing +Z

    # Camera at +Z (looking down at origin) -> Facing
    cam_pos = np.array([0, 0, 1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is True

    # Camera at -Z (looking up at origin) -> Not facing (flipped)
    cam_pos = np.array([0, 0, -1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is False

    # Camera at 45 degree angle
    cam_pos = np.array([1, 0, 1])
    # dot product is cos(45) = 0.707 > 0.15
    assert is_facing_camera(tag_pos, tag_normal, cam_pos) is True

    # Camera at 85 degree angle
    # cos(85) = 0.087 < 0.15
    cam_pos = np.array([np.tan(np.radians(85)), 0, 1])
    assert is_facing_camera(tag_pos, tag_normal, cam_pos, min_dot=0.15) is False


def test_project_points_basic():
    # Camera at (0, 0, 1) looking at origin (0, 0, 0)
    # Forward is (0, 0, -1)
    cam_pos = np.array([0, 0, 1])
    np.eye(3)  # This is a bit simplified, but let's test a point on axis
    # In my look_at_rotation, forward (0,0,-1) with up (0,0,1) handled:
    from render_tag.generation.math import look_at_rotation, make_transformation_matrix

    R = look_at_rotation(np.array([0, 0, -1]))
    cam2world = make_transformation_matrix(cam_pos, R)

    # Simple intrinsics: 100 f, 320 cx, 240 cy
    K = np.array([[100, 0, 320], [0, 100, 240], [0, 0, 1]])

    # Point at origin
    pts = np.array([[0, 0, 0]])
    coords = project_points(pts, cam2world, [640, 480], K.tolist())

    # Point at origin is 1 unit in front of camera at (0,0,1)
    # In camera space it should be at (0, 0, 1) (if camera Z is forward)
    # Or (0, 0, -1) (if camera -Z is forward)
    # My project_points uses inverse(cam2world), so points_cam = R^T (P - C)
    # P-C = (0,0,0) - (0,0,1) = (0,0,-1)
    # R^T (0,0,-1) -> should be on camera Z axis

    assert coords.shape == (1, 2)
    assert coords[0, 0] == pytest.approx(320.0)
    assert coords[0, 1] == pytest.approx(240.0)


def test_validate_visibility_metrics():
    # unit square in image center
    corners = np.array([[310, 230], [330, 230], [330, 250], [310, 250]])
    width, height = 640, 480

    is_vis, metrics = validate_visibility_metrics(corners, width, height, min_area_pixels=100)
    assert is_vis is True
    assert metrics["area"] == pytest.approx(400.0)
    assert metrics["visible_corners"] == 4

    # Half out-of-bounds
    corners_off = np.array([[-10, 230], [10, 230], [10, 250], [-10, 250]])
    is_vis, metrics = validate_visibility_metrics(corners_off, width, height, min_visible_corners=4)
    assert is_vis is False
    assert metrics["visible_corners"] == 2
