"""
Integration tests for 3D-Anchored Orientation Invariance.
Verifies that projected 2D corners maintain logical consistency across rotations.
"""

import numpy as np

from render_tag.generation.projection_math import (
    get_world_matrix,
    project_points,
    validate_winding_order,
)


def test_orientation_invariance_upright():
    """Verify Logical Corner 0 is visual Top-Left when upright."""
    # 1. Setup logical corners (Z-up, Y-forward)
    # TL, TR, BR, BL
    half = 0.05
    keypoints_3d = np.array(
        [
            [-half, half, 0.0],  # 0: TL
            [half, half, 0.0],  # 1: TR
            [half, -half, 0.0],  # 2: BR
            [-half, -half, 0.0],  # 3: BL
        ]
    )

    # 2. Upright pose: facing camera at (0,0,1) looking down
    # Tag at origin, no rotation
    tag_world_mat = get_world_matrix([0, 0, 0], [0, 0, 0])

    # Camera at (0,0,1) looking at origin
    # OpenCV camera: Z forward, Y down, X right
    # To look down from +Z, camera needs 0 rotation in our convention.
    # But let's use a simpler identity camera for math verification.
    cam_world_mat = np.eye(4)
    cam_world_mat[:3, 3] = [0, 0, 1]  # 1m above

    res = [100, 100]
    # Simple K matrix: f=100, cx=50, cy=50
    k_matrix = [[100, 0, 50], [0, 100, 50], [0, 0, 1]]

    # Transform keypoints to world space
    world_kps = (tag_world_mat @ np.hstack([keypoints_3d, np.ones((4, 1))]).T).T[:, :3]

    # Project
    pixels = project_points(world_kps, cam_world_mat, res, k_matrix)

    # 3. Assertions
    # In Y-down (OpenCV), (0,0) is TL.
    # For a centered tag, Logical TL (0) should have smallest x and smallest y.
    sums = [p[0] + p[1] for p in pixels]
    assert np.argmin(sums) == 0
    print(f"Upright pixels: {pixels}")


def test_orientation_invariance_inverted():
    """Verify Logical Corner 0 is visual Bottom-Right when rolled 180."""
    half = 0.05
    keypoints_3d = np.array(
        [
            [-half, half, 0.0],  # 0: TL
            [half, half, 0.0],  # 1: TR
            [half, -half, 0.0],  # 2: BR
            [-half, -half, 0.0],  # 3: BL
        ]
    )

    # Inverted pose: 180 degree roll (rotation around Z)
    tag_world_mat = get_world_matrix([0, 0, 0], [0, 0, np.pi])

    cam_world_mat = np.eye(4)
    cam_world_mat[:3, 3] = [0, 0, 1]
    res = [100, 100]
    k_matrix = [[100, 0, 50], [0, 100, 50], [0, 0, 1]]

    world_kps = (tag_world_mat @ np.hstack([keypoints_3d, np.ones((4, 1))]).T).T[:, :3]
    pixels = project_points(world_kps, cam_world_mat, res, k_matrix)

    # 3. Assertions
    # Rolled 180: Logical TL (0) is now at visual Bottom-Right (max x+y)
    sums = [p[0] + p[1] for p in pixels]
    assert np.argmax(sums) == 0
    print(f"Inverted pixels: {pixels}")


def test_orientation_invariance_skew_winding():
    """Verify Clockwise winding is maintained under extreme skew."""
    half = 0.05
    keypoints_3d = np.array(
        [
            [-half, half, 0.0],  # 0: TL
            [half, half, 0.0],  # 1: TR
            [half, -half, 0.0],  # 2: BR
            [-half, -half, 0.0],  # 3: BL
        ]
    )

    # Extreme pitch (60 deg)
    tag_world_mat = get_world_matrix([0, 0, 0], [np.radians(60), 0, 0])

    cam_world_mat = np.eye(4)
    cam_world_mat[:3, 3] = [0, 0, 1]
    res = [100, 100]
    k_matrix = [[100, 0, 50], [0, 100, 50], [0, 0, 1]]

    world_kps = (tag_world_mat @ np.hstack([keypoints_3d, np.ones((4, 1))]).T).T[:, :3]
    pixels = project_points(world_kps, cam_world_mat, res, k_matrix)

    # Verify CW winding
    assert validate_winding_order(pixels) is True
