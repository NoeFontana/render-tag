"""
Simplified camera intrinsics extractor for the worker.
The K-matrix is now pre-calculated on the host side.
"""

from typing import Any


def resolve_intrinsics(camera_recipe: dict[str, Any]) -> dict[str, Any]:
    """Extracts pre-calculated intrinsics from a Recipe.

    Args:
        camera_recipe: Dictionary following the CameraRecipe schema.

    Returns:
        Dictionary with:
            - resolution: [width, height]
            - k_matrix: 3x3 list of lists
            - fx, fy, cx, cy: extracted from k_matrix
    """
    intrinsics = camera_recipe.get("intrinsics", {})

    # We expect the host to have baked these in according to the rationalized schema
    resolution = intrinsics.get("resolution", [640, 480])
    k_matrix = intrinsics.get("k_matrix")

    if not k_matrix:
        # Emergency fallback for legacy recipes during transition
        # Standard 60 deg horizontal FOV fallback
        import math

        fx = fy = resolution[0] / (2.0 * math.tan(math.radians(60.0 / 2.0)))
        cx, cy = resolution[0] / 2.0, resolution[1] / 2.0
        k_matrix = [
            [float(fx), 0.0, float(cx)],
            [0.0, float(fy), float(cy)],
            [0.0, 0.0, 1.0],
        ]
    else:
        fx = k_matrix[0][0]
        fy = k_matrix[1][1]
        cx = k_matrix[0][2]
        cy = k_matrix[1][2]

    return {
        "resolution": resolution,
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(cx),
        "cy": float(cy),
        "k_matrix": k_matrix,
    }
