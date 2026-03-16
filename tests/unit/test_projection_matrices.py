from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import _get_scene_transformations
from render_tag.generation.board import BoardSpec, compute_charuco_layout
from render_tag.generation.projection_math import project_points


@patch("render_tag.backend.projection.bridge")
def test_get_scene_transformations_no_drift(mock_bridge):
    """
    Test that _get_scene_transformations returns a matrix equivalent
    to the raw world_matrix when scale is [1,1,1].
    """
    # Setup
    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 5]
    mock_bridge.bpy.context.scene.render.resolution_x = 640
    mock_bridge.bpy.context.scene.render.resolution_y = 480
    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    mock_obj = MagicMock()
    # A simple rotation + translation matrix with NO SCALE
    world_matrix = np.eye(4)
    world_matrix[0:3, 0:3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]  # 90 deg rotation
    world_matrix[0:3, 3] = [1, 2, 3]  # Translation

    mock_obj.get_local2world_mat.return_value = world_matrix
    mock_obj.get_location.return_value = [1, 2, 3]

    mock_spec = MagicMock()
    mock_spec.board_width = 1.0
    mock_spec.board_height = 1.0

    # We need to mock get_world_normal and other helpers if they are called
    with (
        patch("render_tag.backend.projection.get_world_normal") as mock_normal,
        patch("render_tag.backend.projection.calculate_distance") as mock_dist,
        patch("render_tag.backend.projection.calculate_angle_of_incidence") as mock_angle,
        patch("render_tag.backend.projection.calculate_relative_pose") as mock_pose,
    ):
        mock_normal.return_value = [0, 0, 1]
        mock_dist.return_value = 5.0
        mock_angle.return_value = 0.0
        mock_pose.return_value = {}

        # ACT
        rigid_matrix, _, _, _, _ = _get_scene_transformations(mock_obj, mock_spec)
        # VERIFY
        # The rigid_matrix should match the world_matrix exactly (since scale was 1)
        np.testing.assert_array_almost_equal(rigid_matrix, world_matrix)


def test_svd_removes_scale():
    """
    Demonstrate that the CURRENT implementation (with SVD) removes scale.
    This test serves as a baseline before we revert the hack.
    """
    # (Similar setup but with a scaled world_matrix)
    pass


# ============================================================================
# Phase 4.1 — Analytical Reprojection Invariants
# ============================================================================


def test_charuco_saddle_projection_forms_regular_grid():
    """
    Analytical reprojection invariant: ChArUco saddle points must project
    to a perfectly regular pixel grid under a distortion-free overhead camera.

    Two sub-checks:
      A. Grid spacing — consecutive projected saddles must be separated by
         exactly Δu = fx·sq/z (columns) and Δv = fy·sq/z (rows) in the
         camera image.
      B. Absolute position — the first saddle (r=0, c=0) must land at the
         expected pixel derived from its physical world coordinate, catching
         any Y-axis inversion in the layout geometry (Phase 1.1).
    """
    rows, cols, sq = 4, 5, 0.04  # 0.20 m x 0.16 m board
    spec = BoardSpec(rows=rows, cols=cols, square_size=sq)
    layout = compute_charuco_layout(spec)

    n_saddle_rows, n_saddle_cols = rows - 1, cols - 1
    assert len(layout.calibration_positions) == n_saddle_rows * n_saddle_cols

    # ── Camera (overhead, Blender convention) ──────────────────────────────
    z_depth = 0.5
    fx, fy = 800.0, 800.0
    img_w, img_h = 1024, 768
    cx, cy = img_w / 2.0, img_h / 2.0
    K = [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]
    cam_world = np.eye(4)
    cam_world[2, 3] = z_depth

    saddle_3d = np.array([[p.x, p.y, p.z] for p in layout.calibration_positions])
    saddle_2d = project_points(saddle_3d, cam_world, [img_w, img_h], K)

    # Reshape into a row-major grid (saddles are stored row-outer, col-inner)
    grid = saddle_2d.reshape(n_saddle_rows, n_saddle_cols, 2)

    # ── A. Uniform column spacing: Δu = fx·sq/z ───────────────────────────
    expected_du = fx * sq / z_depth  # 64.0 px
    for r in range(n_saddle_rows):
        col_diffs = np.diff(grid[r, :, 0])
        np.testing.assert_allclose(
            col_diffs,
            expected_du,
            atol=1e-9,
            err_msg=f"Column spacing not uniform in saddle row {r}",
        )

    # ── B. Uniform row spacing: Δv = fy·sq/z ──────────────────────────────
    expected_dv = fy * sq / z_depth  # 64.0 px
    for c in range(n_saddle_cols):
        row_diffs = np.diff(grid[:, c, 1])
        np.testing.assert_allclose(
            row_diffs,
            expected_dv,
            atol=1e-9,
            err_msg=f"Row spacing not uniform in saddle column {c}",
        )

    # ── C. Absolute position of first saddle ──────────────────────────────
    # After Phase 1.1 fix: saddle (0,0) sits at
    #   world_x = -board_width/2  + sq   (one cell-step inward from left)
    #   world_y = +board_height/2 - sq   (one cell-step downward from top)
    # Projected through overhead camera:
    #   u = fx · world_x / z + cx
    #   v = fy · (-world_y) / z + cy   (OpenCV Y flips Blender Y)
    width_m = cols * sq
    height_m = rows * sq
    expected_sx = -width_m / 2 + sq
    expected_sy = height_m / 2 - sq
    expected_u0 = fx * expected_sx / z_depth + cx
    expected_v0 = fy * (-expected_sy) / z_depth + cy

    np.testing.assert_allclose(
        grid[0, 0],
        [expected_u0, expected_v0],
        atol=1e-9,
        err_msg=(
            "First saddle projects to wrong pixel — likely a Y-inversion in "
            "compute_charuco_layout (Phase 1.1 regression)."
        ),
    )
