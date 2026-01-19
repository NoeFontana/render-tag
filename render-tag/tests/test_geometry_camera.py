"""
Unit tests for camera_geometry module.
"""

from __future__ import annotations

import numpy as np
from render_tag.geometry.camera import sample_camera_pose, validate_camera_pose


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
    assert (
        validate_camera_pose(pose_ok, look_at, min_distance=0.5, min_height=0.1) is True
    )

    # Too close
    assert validate_camera_pose(pose_ok, look_at, min_distance=1.5) is False

    # Too low
    pose_low = sample_camera_pose(look_at, distance=1.0, elevation=0.01)  # Very low
    assert validate_camera_pose(pose_low, look_at, min_height=0.1) is False
