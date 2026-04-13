"""
Tests for the spherical equidistant distortion remap correctness.

Core invariant: for any 3D point P, the pixel produced by project_points (forward
KB distortion through K_target) must equal the pixel that compute_spherical_distortion_maps
says it came from in the equidistant render — which must also equal the analytically
computed equidistant projection of P.

Additionally tests compute_spherical_overscan_params for correct θ_max, margin, and
resolution calculation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from render_tag.backend.distortion import compute_spherical_distortion_maps
from render_tag.generation.compiler import compute_spherical_overscan_params
from render_tag.generation.projection_math import get_opencv_camera_matrix, project_points

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Moderate focal length — typical for a fisheye lens on a 640x480 sensor.
K_TARGET = [[300.0, 0.0, 320.0], [0.0, 300.0, 240.0], [0.0, 0.0, 1.0]]
RESOLUTION = [640, 480]

# Non-trivial KB coefficients (mild wide-angle fisheye).
KB_COEFFS = [-0.0035, 0.0015, -0.0003, 0.0001]

# Blender camera matrix whose get_opencv_camera_matrix() result is identity.
# get_opencv_camera_matrix flips columns 1 and 2, so we need col1=[0,-1,0,0]
# and col2=[0,0,-1,0] so that -col1=[0,1,0,0] and -col2=[0,0,1,0] → eye(4).
CAM_WORLD = np.diag([1.0, -1.0, -1.0, 1.0])

# Margin used by compute_spherical_overscan_params.
MARGIN_DEG = 2.0


def _analytic_equidistant_pixel(
    point_world: np.ndarray,
    cam_world: np.ndarray,
    fov_spherical: float,
    resolution_spherical: list[int],
) -> tuple[float, float]:
    """Analytically compute where a 3D world point projects in an equidistant render.

    Mirrors the coordinate path used by project_points:
        opencv_c2w = get_opencv_camera_matrix(cam_world)  # Blender→OpenCV flip
        world_to_cam = inv(opencv_c2w)
        p_cam = world_to_cam @ P_world
        x_u = p_cam[0] / p_cam[2],  y_u = p_cam[1] / p_cam[2]
        θ = atan(sqrt(x_u² + y_u²))
        φ = atan2(y_u, x_u)
        r = R_max * θ / θ_max_render
    """
    opencv_c2w = get_opencv_camera_matrix(np.array(cam_world, dtype=np.float64))
    world_to_cam = np.linalg.inv(opencv_c2w)
    p_h = np.append(point_world.astype(np.float64), 1.0)
    p_cam = (world_to_cam @ p_h)[:3]
    x_u = p_cam[0] / p_cam[2]
    y_u = p_cam[1] / p_cam[2]

    rho = math.sqrt(x_u**2 + y_u**2)
    theta = math.atan(rho)
    phi = math.atan2(y_u, x_u)

    R_max = resolution_spherical[0] / 2.0
    cx_sph = R_max
    cy_sph = resolution_spherical[1] / 2.0
    theta_max_render = fov_spherical / 2.0

    r_pixel = R_max * theta / theta_max_render
    u_eq = cx_sph + r_pixel * math.cos(phi)
    v_eq = cy_sph + r_pixel * math.sin(phi)
    return u_eq, v_eq


# ---------------------------------------------------------------------------
# Remap consistency: annotation pixel == remap source pixel == analytic pixel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "point",
    [
        np.array([0.05, -0.03, 1.0]),  # Slight off-axis
        np.array([0.15, 0.10, 1.0]),  # Moderate off-axis
        np.array([-0.20, 0.05, 0.8]),  # Off-axis + different depth
        np.array([0.0, 0.0, 1.0]),  # Optical centre (singularity θ=0)
    ],
)
def test_spherical_remap_annotation_consistency(point: np.ndarray) -> None:
    """Annotated pixel must map back to the same equidistant source as analytic projection."""
    fov_spherical, res_spherical = compute_spherical_overscan_params(
        K_TARGET, tuple(RESOLUTION), KB_COEFFS
    )
    res_sph = list(res_spherical)

    # 1. Annotation pixel via forward KB distortion through K_target.
    px_ann = project_points(
        point[np.newaxis],
        CAM_WORLD,
        RESOLUTION,
        K_TARGET,
        KB_COEFFS,
        "kannala_brandt",
    )
    u_ann, v_ann = float(px_ann[0, 0]), float(px_ann[0, 1])

    # 2. Remap source pixel from the backward spherical map at the annotation pixel.
    map_x, map_y = compute_spherical_distortion_maps(
        K_TARGET, RESOLUTION, KB_COEFFS, fov_spherical, res_sph
    )
    H, W = map_x.shape
    ui, vi = round(u_ann), round(v_ann)
    assert 0 <= ui < W and 0 <= vi < H, f"Annotation pixel ({ui}, {vi}) outside remap grid"
    u_src = float(map_x[vi, ui])
    v_src = float(map_y[vi, ui])

    # 3. Analytic equidistant projection of the same point.
    u_eq, v_eq = _analytic_equidistant_pixel(point, CAM_WORLD, fov_spherical, res_sph)

    # Remap source and analytic projection must agree to within 0.6 px.
    # (Rounding to the nearest integer pixel introduces at most 0.5 px error.)
    assert abs(u_src - u_eq) < 0.6, (
        f"Remap source u={u_src:.3f} != analytic u={u_eq:.3f} for point {point}"
    )
    assert abs(v_src - v_eq) < 0.6, (
        f"Remap source v={v_src:.3f} != analytic v={v_eq:.3f} for point {point}"
    )


# ---------------------------------------------------------------------------
# compute_spherical_overscan_params: parameter correctness
# ---------------------------------------------------------------------------


def test_spherical_overscan_params_margin() -> None:
    """fov_spherical includes exactly the configured margin beyond θ_max."""
    fov, _ = compute_spherical_overscan_params(
        K_TARGET, tuple(RESOLUTION), KB_COEFFS, margin_deg=MARGIN_DEG
    )
    fov_no_margin, _ = compute_spherical_overscan_params(
        K_TARGET, tuple(RESOLUTION), KB_COEFFS, margin_deg=0.0
    )
    margin_rad = math.radians(MARGIN_DEG)
    assert abs((fov - fov_no_margin) - 2.0 * margin_rad) < 1e-9, (
        "fov_spherical must exceed zero-margin FOV by exactly 2 * margin"
    )


def test_spherical_overscan_params_resolution_density() -> None:
    """Resolution R satisfies R >= 2 * fx * θ_max_render (px/rad ≥ fx)."""
    fov, (R_w, R_h) = compute_spherical_overscan_params(
        K_TARGET, tuple(RESOLUTION), KB_COEFFS, margin_deg=MARGIN_DEG
    )
    fx = K_TARGET[0][0]
    theta_max_render = fov / 2.0
    assert R_w == R_h, "Intermediate render must be square"
    assert R_w >= 2 * fx * theta_max_render, (
        f"R={R_w} must be >= 2*fx*θ_max_render={2 * fx * theta_max_render:.1f}"
    )


def test_spherical_overscan_params_fov_positive() -> None:
    """fov_spherical must be strictly positive and less than π (hemisphere)."""
    fov, _ = compute_spherical_overscan_params(K_TARGET, tuple(RESOLUTION), KB_COEFFS)
    assert 0.0 < fov < math.pi, f"fov_spherical={fov:.4f} rad must be in (0, π)"


def test_spherical_distortion_maps_shape() -> None:
    """compute_spherical_distortion_maps returns arrays with correct shape."""
    fov, res_sph = compute_spherical_overscan_params(K_TARGET, tuple(RESOLUTION), KB_COEFFS)
    map_x, map_y = compute_spherical_distortion_maps(
        K_TARGET, RESOLUTION, KB_COEFFS, fov, list(res_sph)
    )
    H, W = RESOLUTION[1], RESOLUTION[0]
    assert map_x.shape == (H, W), f"map_x shape {map_x.shape} != ({H}, {W})"
    assert map_y.shape == (H, W), f"map_y shape {map_y.shape} != ({H}, {W})"
    assert map_x.dtype == np.float32
    assert map_y.dtype == np.float32


def test_spherical_distortion_maps_centre_at_centre() -> None:
    """The optical centre pixel must map to the centre of the equidistant render."""
    fov, res_sph = compute_spherical_overscan_params(K_TARGET, tuple(RESOLUTION), KB_COEFFS)
    res_sph_list = list(res_sph)
    map_x, map_y = compute_spherical_distortion_maps(
        K_TARGET, RESOLUTION, KB_COEFFS, fov, res_sph_list
    )
    cx_tgt = int(K_TARGET[0][2])  # principal point x
    cy_tgt = int(K_TARGET[1][2])  # principal point y
    cx_sph = res_sph_list[0] / 2.0
    cy_sph = res_sph_list[1] / 2.0
    assert abs(map_x[cy_tgt, cx_tgt] - cx_sph) < 1.0, (
        f"Centre pixel x={map_x[cy_tgt, cx_tgt]:.2f} should be near {cx_sph:.2f}"
    )
    assert abs(map_y[cy_tgt, cx_tgt] - cy_sph) < 1.0, (
        f"Centre pixel y={map_y[cy_tgt, cx_tgt]:.2f} should be near {cy_sph:.2f}"
    )
