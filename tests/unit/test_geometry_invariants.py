from __future__ import annotations

import numpy as np
import pytest

from render_tag.generation.projection_math import (
    get_world_normal,
    sanitize_to_rigid_transform,
)


def test_sanitize_to_rigid_transform_invariants():
    """
    Assert that sanitize_to_rigid_transform restores SO(3) and SE(3) invariants.
    """
    # 1. Extreme non-uniform scaling: X=10, Y=0.1, Z=5
    scale = np.diag([10.0, 0.1, 5.0, 1.0])
    
    # Rotation 45 deg around Z
    theta = np.pi / 4
    c, s = np.cos(theta), np.sin(theta)
    rot = np.eye(4)
    rot[:2, :2] = [[c, -s], [s, c]]
    
    # Translation
    trans = np.eye(4)
    trans[:3, 3] = [1.2, 3.4, 5.6]
    
    # Affine matrix (Graphics Layer)
    affine_matrix = trans @ rot @ scale
    
    # Sanitize (Perception Layer)
    sanitized = sanitize_to_rigid_transform(affine_matrix)
    
    # Assertions
    # A. Det(R) should be +1.0
    r_block = sanitized[:3, :3]
    assert np.isclose(np.linalg.det(r_block), 1.0, atol=1e-6)
    
    # B. Orthogonality: R.T @ R == I
    np.testing.assert_allclose(r_block.T @ r_block, np.eye(3), atol=1e-6)
    
    # C. Translation is preserved
    np.testing.assert_allclose(sanitized[:3, 3], [1.2, 3.4, 5.6], atol=1e-6)


def test_covariant_normal_preservation():
    """
    Assert that world normals remain perpendicular to surface manifolds under scaling.
    """
    # Define a pure rotation (Z-up)
    world_matrix_rigid = np.eye(4)
    
    # Local Z normal
    local_normal = np.array([0, 0, 1])
    
    # Local tangent vectors (X and Y)
    local_tangent_x = np.array([1, 0, 0])
    local_tangent_y = np.array([0, 1, 0])
    
    # Apply non-uniform scaling (S_x=5, S_y=0.2, S_z=1.0)
    scale_matrix = np.diag([5.0, 0.2, 1.0, 1.0])
    world_matrix_scaled = world_matrix_rigid @ scale_matrix
    
    # Compute World Normal using the new inverse-transpose method
    world_normal = get_world_normal(world_matrix_scaled, local_normal)
    
    # Compute World Tangents (standard point/vector transformation)
    # We must normalize them to check perpendicularity via dot product
    world_tangent_x = (world_matrix_scaled[:3, :3] @ local_tangent_x)
    world_tangent_y = (world_matrix_scaled[:3, :3] @ local_tangent_y)
    
    # Assertions
    # The normal should be perpendicular to all vectors in the tangent plane
    dot_x = np.dot(world_normal, world_tangent_x)
    dot_y = np.dot(world_normal, world_tangent_y)
    
    assert np.isclose(dot_x, 0.0, atol=1e-6), f"Normal not perpendicular to Tangent X: dot={dot_x}"
    assert np.isclose(dot_y, 0.0, atol=1e-6), f"Normal not perpendicular to Tangent Y: dot={dot_y}"


def test_positional_consistency():
    """
    Assert that metric points transformed by the rigid matrix compute to 
    the exact same world-space position as unscaled references.
    """
    # Procedural local coordinates (metric)
    local_points = np.array([
        [-0.5, -0.5, 0.0],
        [0.5, -0.5, 0.0],
        [0.5, 0.5, 0.0],
        [-0.5, 0.5, 0.0]
    ])
    
    # Rigid transformation (Reference)
    trans = [10, 20, 30]
    world_matrix_rigid = np.eye(4)
    world_matrix_rigid[:3, 3] = trans
    
    # Scaled graphics matrix
    world_matrix_scaled = world_matrix_rigid.copy()
    world_matrix_scaled[:3, :3] *= 5.0 # Uniform scale
    
    # Sanitized matrix
    sanitized = sanitize_to_rigid_transform(world_matrix_scaled)
    
    # Transform points
    # 1. Reference transform
    expected_world = (world_matrix_rigid[:3, :3] @ local_points.T).T + world_matrix_rigid[:3, 3]
    
    # 2. Sanitized transform
    actual_world = (sanitized[:3, :3] @ local_points.T).T + sanitized[:3, 3]
    
    # Assertions
    np.testing.assert_allclose(actual_world, expected_world, atol=1e-6)
