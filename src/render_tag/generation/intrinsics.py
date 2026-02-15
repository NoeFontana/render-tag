"""
Pure-Python utilities for resolving camera intrinsics from recipes.
Isolates geometry logic from Blender dependencies for testability.
"""

import math
from typing import Any


def resolve_intrinsics(camera_recipe: dict[str, Any]) -> dict[str, Any]:
    """Resolves camera parameters (resolution, K-matrix, etc.) from a Recipe.

    Args:
        camera_recipe: Dictionary following the CameraRecipe schema.

    Returns:
        Dictionary with:
            - resolution: [width, height]
            - fov: float
            - fx, fy: focal lengths
            - cx, cy: principal point
            - k_matrix: 3x3 list of lists
    """
    intrinsics_block = camera_recipe.get("intrinsics", {})

    # Extract baseline
    # Priority: intrinsics_block["resolution"] -> top_level["resolution"] -> default
    resolution = intrinsics_block.get("resolution") or camera_recipe.get("resolution") or [640, 480]
    fov = intrinsics_block.get("fov") or camera_recipe.get("fov") or 60.0

    # Extract explicit parameters from the nested 'intrinsics' dict
    # (Corresponds to CameraIntrinsics.intrinsics field)
    explicit = intrinsics_block.get("intrinsics", {})
    if not isinstance(explicit, dict):
        explicit = {}

    k_matrix = explicit.get("k_matrix")

    if k_matrix:
        # If K matrix is provided, it dictates the focal lengths and principal point
        fx = k_matrix[0][0]
        fy = k_matrix[1][1]
        cx = k_matrix[0][2]
        cy = k_matrix[1][2]
    else:
        # Compute from focal lengths or FOV
        f_length = explicit.get("focal_length")
        f_x = explicit.get("focal_length_x")
        f_y = explicit.get("focal_length_y")

        if f_x is not None and f_y is not None:
            fx, fy = float(f_x), float(f_y)
        elif f_length is not None:
            fx = fy = float(f_length)
        else:
            # Standard FOV-to-Pixel Focal Length conversion
            fx = fy = resolution[0] / (2.0 * math.tan(math.radians(fov / 2.0)))

        cx = explicit.get("principal_point_x")
        if cx is None:
            cx = resolution[0] / 2.0

        cy = explicit.get("principal_point_y")
        if cy is None:
            cy = resolution[1] / 2.0

        k_matrix = [
            [float(fx), 0.0, float(cx)],
            [0.0, float(fy), float(cy)],
            [0.0, 0.0, 1.0],
        ]

    return {
        "resolution": resolution,
        "fov": float(fov),
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(cx),
        "cy": float(cy),
        "k_matrix": k_matrix,
    }
