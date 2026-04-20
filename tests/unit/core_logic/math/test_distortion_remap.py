"""
Tests for the distortion remap correctness.

Core invariant: for any 3D point P, the pixel produced by project_points (forward
distortion through K_target) must equal the pixel that compute_distortion_maps
says it came from in the overscan image — after being forward-projected through
K_linear.

In other words the remap and annotation pipelines must agree: annotated corners
must land exactly on the visual content after the warp.
"""

from __future__ import annotations

import numpy as np
import pytest

from render_tag.backend.distortion import compute_distortion_maps
from render_tag.core.geometry.projection_math import (
    project_points,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

K_TARGET = [[800.0, 0.0, 480.0], [0.0, 800.0, 270.0], [0.0, 0.0, 1.0]]
K_LINEAR = [[880.0, 0.0, 528.0], [0.0, 880.0, 297.0], [0.0, 0.0, 1.0]]
RESOLUTION = [960, 540]

BC_COEFFS = [-0.28, 0.08, 0.0002, 0.0001, 0.0]
KB_COEFFS = [-0.0035, 0.0015, -0.0003, 0.0001]

# Blender camera matrix whose get_opencv_camera_matrix() result is identity.
# get_opencv_camera_matrix flips columns 1 and 2, so we need col1=[0,-1,0,0]
# and col2=[0,0,-1,0] so that -col1=[0,1,0,0] and -col2=[0,0,1,0] → eye(4).
# This places the camera at the origin looking down +Z in OpenCV (camera) space.
CAM_WORLD = np.diag([1.0, -1.0, -1.0, 1.0])


def _make_point_in_front(x_m: float = 0.05, y_m: float = -0.03, z_m: float = 1.0) -> np.ndarray:
    """Return a single 3D world point visible in front of the camera."""
    return np.array([[x_m, y_m, z_m]])


# ---------------------------------------------------------------------------
# Remap consistency: annotation pixel == remap source pixel
#
# For a 3D point P:
#   - project_points with K_target + forward distortion  → (u_ann, v_ann)
#   - compute_distortion_maps at (u_ann, v_ann)           → (u_src, v_src) in overscan
#   - project_points with K_linear (no distortion)        → (u_lin, v_lin) in overscan
#
# Invariant: (u_src, v_src) == (u_lin, v_lin)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model, coeffs",
    [
        ("brown_conrady", BC_COEFFS),
        ("kannala_brandt", KB_COEFFS),
    ],
)
def test_remap_annotation_consistency(model: str, coeffs: list[float]) -> None:
    """Annotated pixel must map back to the same source as the linear projection."""
    pts = _make_point_in_front()

    # 1. Annotation pixel: project through K_target with distortion
    px_ann = project_points(pts, CAM_WORLD, RESOLUTION, K_TARGET, coeffs, model)
    u_ann, v_ann = float(px_ann[0, 0]), float(px_ann[0, 1])

    # 2. Remap source pixel: look up the backward map at the annotation pixel
    map_x, map_y = compute_distortion_maps(K_LINEAR, K_TARGET, RESOLUTION, coeffs, model)
    H, W = map_x.shape
    ui, vi = round(u_ann), round(v_ann)
    assert 0 <= ui < W and 0 <= vi < H, "Annotation pixel is outside the remap grid"
    u_src = float(map_x[vi, ui])
    v_src = float(map_y[vi, ui])

    # 3. Linear projection pixel: project through K_linear (no distortion)
    px_lin = project_points(pts, CAM_WORLD, RESOLUTION, K_LINEAR)
    u_lin, v_lin = float(px_lin[0, 0]), float(px_lin[0, 1])

    # The remap source must agree with the linear projection to within 0.5 px
    # (rounding to the nearest integer pixel introduces at most 0.5 px error).
    assert abs(u_src - u_lin) < 0.6, f"{model}: remap source u={u_src:.3f} != linear u={u_lin:.3f}"
    assert abs(v_src - v_lin) < 0.6, f"{model}: remap source v={v_src:.3f} != linear v={v_lin:.3f}"
