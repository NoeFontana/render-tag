"""
Post-render lens distortion warp for render-tag.

Implements the linear-overscan post-warp approach: Blender renders a larger
linear (pinhole) image, and this module remaps it to the correct distorted
output via a dense forward-distortion pixel map.
"""

from __future__ import annotations

import cv2
import numpy as np


def compute_distortion_maps(
    k_linear: list[list[float]],
    k_target: list[list[float]],
    resolution_target: list[int],
    distortion_coeffs: list[float],
    distortion_model: str = "brown_conrady",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the (map_x, map_y) pixel coordinate arrays for cv2.remap.

    cv2.remap is a *backward* map: for each destination pixel (u, v) in the
    distorted output image, (map_x[v,u], map_y[v,u]) gives the source pixel
    to sample in the linear overscan image. The path is:
      1. Grid of target pixels → cv2.undistortPoints (or fisheye variant) →
         undistorted normalized rays.  OpenCV's C++ solver handles the iterative
         inverse distortion in hardware-accelerated code.
      2. Undistorted rays → project through K_linear → source overscan pixels.

    Separate from apply_lens_distortion_warp so callers can compute the maps
    once and reuse them across multiple images (e.g. RGB + segmap).

    Args:
        k_linear: 3x3 overscan K-matrix [[fx,0,cx],[0,fy,cy],[0,0,1]].
        k_target: 3x3 target K-matrix (distorted camera, used for PnP).
        resolution_target: [W, H] of the output distorted image.
        distortion_coeffs: Distortion coefficients for the model.
        distortion_model: 'brown_conrady' (default) or 'kannala_brandt'.

    Returns:
        (map_x, map_y): float32 arrays of shape (H, W), ready for cv2.remap.
    """
    W_tgt, H_tgt = resolution_target
    K_tgt = np.array(k_target, dtype=np.float64)
    D = np.array(distortion_coeffs, dtype=np.float64)

    u_tgt, v_tgt = np.meshgrid(np.arange(W_tgt), np.arange(H_tgt))
    pts = np.stack([u_tgt, v_tgt], axis=-1).reshape(-1, 1, 2).astype(np.float64)

    # Delegate inverse distortion to OpenCV's C++ solver.
    # undistortPoints / fisheye.undistortPoints apply K^-1 then iteratively
    # remove the distortion model, returning ideal normalized coordinates.
    if distortion_model == "kannala_brandt":
        rays = cv2.fisheye.undistortPoints(pts, K_tgt, D)
    else:
        rays = cv2.undistortPoints(pts, K_tgt, D)

    rays = rays.reshape(H_tgt, W_tgt, 2)
    map_x = (rays[..., 0] * k_linear[0][0] + k_linear[0][2]).astype(np.float32)
    map_y = (rays[..., 1] * k_linear[1][1] + k_linear[1][2]).astype(np.float32)
    return map_x, map_y


def compute_spherical_distortion_maps(
    k_target: list[list[float]],
    resolution_target: list[int],
    distortion_coeffs: list[float],
    fov_spherical: float,
    resolution_spherical: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute backward remap maps from a Blender FISHEYE_EQUIDISTANT render to the
    Kannala-Brandt distorted output.

    cv2.remap is a *backward* map: for each destination pixel (u, v) in the distorted
    output, (map_x[v,u], map_y[v,u]) gives the source pixel in the equidistant render.

    The path for each target pixel is:
      1. Unproject through K_target + inverse KB → ideal normalised ray (x_u, y_u).
      2. Incidence angle:  θ = atan(sqrt(x_u² + y_u²))
         Azimuth:          φ = atan2(y_u, x_u)
      3. Equidistant radius: r = R_max * θ / θ_max_render
      4. Source pixel:     (cx_sph + r·cos(φ),  cy_sph + r·sin(φ))

    The singularity at θ = 0 is handled safely: rho = 0 ⟹ r = 0 ⟹ centre pixel.
    Pixels where θ > θ_max_render are mapped to (-1, -1) so cv2.remap returns black.

    Args:
        k_target: 3x3 target K-matrix (distorted KB camera, used for PnP).
        resolution_target: [W, H] of the output distorted image.
        distortion_coeffs: Kannala-Brandt coefficients [k1, k2, k3, k4].
        fov_spherical: Full FOV in radians of the equidistant render (= 2 * θ_max_render).
        resolution_spherical: [R, R] square resolution of the equidistant render.

    Returns:
        (map_x, map_y): float32 arrays of shape (H, W), ready for cv2.remap.
    """
    W_tgt, H_tgt = resolution_target
    center = resolution_spherical[0] / 2.0  # cx == cy == R_max for a square render
    theta_max_render = fov_spherical / 2.0

    K_tgt = np.array(k_target, dtype=np.float64)
    D = np.array(distortion_coeffs, dtype=np.float64)

    u_tgt, v_tgt = np.meshgrid(np.arange(W_tgt), np.arange(H_tgt))
    pts = np.stack([u_tgt, v_tgt], axis=-1).reshape(-1, 1, 2).astype(np.float64)

    # Inverse KB: distorted pixel → ideal normalised ray via OpenCV's C++ solver.
    undist = cv2.fisheye.undistortPoints(pts, K_tgt, D)
    x_u = undist[:, 0, 0]
    y_u = undist[:, 0, 1]

    rho = np.sqrt(x_u ** 2 + y_u ** 2)
    theta = np.arctan(rho).reshape(H_tgt, W_tgt)
    phi = np.arctan2(y_u, x_u).reshape(H_tgt, W_tgt)

    r_pixel = center * theta / theta_max_render
    # Initialize float32 directly to avoid an extra copy at return time.
    u_src = (center + r_pixel * np.cos(phi)).astype(np.float32)
    v_src = (center + r_pixel * np.sin(phi)).astype(np.float32)

    # Pixels beyond the render FOV → invalid coordinate → black border after remap.
    u_src[theta > theta_max_render] = -1.0
    v_src[theta > theta_max_render] = -1.0

    return u_src, v_src


def remap_image(
    img: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
    nearest_neighbor: bool = False,
) -> np.ndarray:
    """
    Apply precomputed distortion maps to an image via cv2.remap.

    Args:
        img: Source image (any shape/dtype cv2.remap accepts).
        map_x: float32 (H, W) x-coordinate map from compute_distortion_maps.
        map_y: float32 (H, W) y-coordinate map from compute_distortion_maps.
        nearest_neighbor: If True, use INTER_NEAREST (for segmentation maps
            to avoid label bleeding). Defaults to Lanczos4 to preserve
            high-frequency marker edges for sub-pixel corner detection.

    Returns:
        Remapped image at the resolution encoded in map_x/map_y.
    """
    import cv2

    interp = cv2.INTER_NEAREST if nearest_neighbor else cv2.INTER_LANCZOS4
    return cv2.remap(
        img, map_x, map_y, interpolation=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )


def apply_lens_distortion_warp(
    img_linear: np.ndarray,
    k_linear: list[list[float]],
    k_target: list[list[float]],
    resolution_target: list[int],
    distortion_coeffs: list[float],
    distortion_model: str = "brown_conrady",
    nearest_neighbor: bool = False,
) -> np.ndarray:
    """
    Remap a linearly-rendered overscan image to the distorted target space.

    Convenience wrapper that computes distortion maps and applies them in one
    call. When warping multiple images with the same parameters (e.g. RGB and
    segmap), prefer compute_distortion_maps + remap_image to avoid recomputing
    the pixel maps.

    Args:
        img_linear: H_lin x W_lin x C ndarray (uint8 or float32).
        k_linear: 3x3 overscan K-matrix [[fx,0,cx],[0,fy,cy],[0,0,1]].
        k_target: 3x3 target K-matrix (distorted camera, used for PnP).
        resolution_target: [W, H] of the output distorted image.
        distortion_coeffs: Distortion coefficients for the model.
        distortion_model: 'brown_conrady' (default) or 'kannala_brandt'.
        nearest_neighbor: If True, use INTER_NEAREST (for segmentation maps).

    Returns:
        Warped image of shape H x W x C at target resolution.
    """
    map_x, map_y = compute_distortion_maps(
        k_linear, k_target, resolution_target, distortion_coeffs, distortion_model
    )
    return remap_image(img_linear, map_x, map_y, nearest_neighbor=nearest_neighbor)
