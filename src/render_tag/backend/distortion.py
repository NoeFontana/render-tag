"""
Post-render lens distortion warp for render-tag.

Implements the linear-overscan post-warp approach: Blender renders a larger
linear (pinhole) image, and this module remaps it to the correct distorted
output via a dense forward-distortion pixel map.
"""

from __future__ import annotations

import numpy as np

from render_tag.generation.projection_math import apply_distortion_by_model


def compute_distortion_maps(
    k_linear: list[list[float]],
    k_target: list[list[float]],
    resolution_target: list[int],
    distortion_coeffs: list[float],
    distortion_model: str = "brown_conrady",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the (map_x, map_y) pixel coordinate arrays for cv2.remap.

    For each output pixel (u, v) in the target distorted image, maps back to
    the corresponding source coordinate in the linear overscan image via the
    forward distortion model.

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
    fx_t = k_target[0][0]
    fy_t = k_target[1][1]
    cx_t = k_target[0][2]
    cy_t = k_target[1][2]
    fx_l = k_linear[0][0]
    fy_l = k_linear[1][1]
    cx_l = k_linear[0][2]
    cy_l = k_linear[1][2]

    u_tgt, v_tgt = np.meshgrid(
        np.arange(W_tgt, dtype=np.float32),
        np.arange(H_tgt, dtype=np.float32),
    )
    x_norm = (u_tgt - cx_t) / fx_t
    y_norm = (v_tgt - cy_t) / fy_t
    x_d, y_d = apply_distortion_by_model(x_norm, y_norm, distortion_coeffs, distortion_model)

    map_x = (x_d * fx_l + cx_l).astype(np.float32)
    map_y = (y_d * fy_l + cy_l).astype(np.float32)
    return map_x, map_y


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
            to avoid label bleeding). Defaults to bilinear interpolation.

    Returns:
        Remapped image at the resolution encoded in map_x/map_y.
    """
    import cv2

    interp = cv2.INTER_NEAREST if nearest_neighbor else cv2.INTER_LINEAR
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
