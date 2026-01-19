"""
Layout generators for render-tag scene composition.

This module positions tags in different layout modes:
- Plain: Tags equidistant in a grid
- ChArUco: Checkerboard pattern (tags in white squares)
- AprilGrid: Kalibr-style grid (tags in every cell)

Position calculations use the tested board_geometry module.
Blender-specific mesh creation is kept separate.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import bpy

# Import board geometry logic
try:
    import os
    import sys

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(scripts_dir))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from render_tag.geometry.board import (
        BoardSpec,
        BoardType,
        compute_charuco_layout,
        compute_aprilgrid_layout,
    )

    GEOMETRY_AVAILABLE = True
except ImportError:
    GEOMETRY_AVAILABLE = False

import blenderproc as bproc

# The BoardType enum is no longer directly imported from board_geometry,
# but is part of BoardSpec. We'll need to adjust its usage if it's used directly.
# For now, remove the old import.
# from board_geometry import (
#     BoardSpec,
#     BoardType,
#     compute_aprilgrid_layout,
#     compute_charuco_layout,
# )

if TYPE_CHECKING:
    from blenderproc.types import MeshObject


# =============================================================================
# Public API
# =============================================================================


def apply_layout(
    tag_objects: list[MeshObject],
    layout_mode: str,
    *,
    spacing: float = 0.05,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    corner_size: float = 0.02,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int | None = None,
    rows: int | None = None,
) -> list[MeshObject]:
    """Apply the specified layout to tag objects.

    Args:
        tag_objects: List of tag mesh objects to position.
        layout_mode: One of "plain", "cb" (ChArUco), or "aprilgrid".
        spacing: Tag spacing for plain layout (meters).
        square_size: Size of each grid square (meters).
        marker_margin: Margin between marker and square edge (meters).
        corner_size: Size of corner squares for AprilGrid (meters).
        center: Center point of the layout.
        cols: Number of columns (auto-calculated if None).
        rows: Number of rows (auto-calculated if None).

    Returns:
        List of additional objects created (black squares, corners).
    """
    if layout_mode == "plain":
        create_plain_layout(tag_objects, spacing=spacing, center=center)
        return []

    if layout_mode == "cb":
        return create_charuco_layout(
            tag_objects,
            square_size=square_size,
            marker_margin=marker_margin,
            center=center,
            cols=cols,
            rows=rows,
        )

    if layout_mode == "aprilgrid":
        return create_aprilgrid_layout(
            tag_objects,
            square_size=square_size,
            marker_margin=marker_margin,
            corner_size=corner_size,
            center=center,
            cols=cols,
            rows=rows,
        )

    # Default to plain
    create_plain_layout(tag_objects, spacing=spacing, center=center)
    return []


def create_plain_layout(
    tag_objects: list[MeshObject],
    *,
    spacing: float = 0.05,
    center: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """Position tags equidistant in a grid with random rotations.

    Args:
        tag_objects: List of tag mesh objects to position.
        spacing: Distance between tag centers (meters).
        center: Center point of the grid.
    """
    n = len(tag_objects)
    if n == 0:
        return

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    grid_width = (cols - 1) * spacing
    grid_height = (rows - 1) * spacing
    start_x = center[0] - grid_width / 2
    start_y = center[1] - grid_height / 2

    for i, tag in enumerate(tag_objects):
        col, row = i % cols, i // cols
        x = start_x + col * spacing
        y = start_y + row * spacing

        tag.set_location([x, y, center[2]])
        tag.set_rotation_euler([0, 0, random.uniform(0, 2 * math.pi)])


def create_charuco_layout(
    tag_objects: list[MeshObject],
    *,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int | None = None,
    rows: int | None = None,
) -> list[MeshObject]:
    """Position tags in a ChArUco board pattern.

    Tags are placed in white squares of a checkerboard pattern.
    Black squares fill alternating positions.

    Args:
        tag_objects: List of tag mesh objects to position.
        square_size: Size of each checkerboard square (meters).
        marker_margin: Margin between marker edge and square edge.
        center: Center point of the board.
        cols: Number of columns (auto-calculated if None).
        rows: Number of rows (auto-calculated if None).

    Returns:
        List of created black square objects.
    """
    n = len(tag_objects)
    if n == 0:
        return []

    # Auto-calculate grid size if not provided
    if cols is None or rows is None:
        total_squares = n * 2
        cols = math.ceil(math.sqrt(total_squares))
        rows = math.ceil(total_squares / cols)

    # Use tested geometry module for positions
    spec = BoardSpec(
        rows=rows,
        cols=cols,
        square_size=square_size,
        marker_margin=marker_margin,
        board_type=BoardType.CHARUCO,
    )
    layout = compute_charuco_layout(spec, center=center)

    # Apply positions to Blender objects
    _apply_tag_positions(tag_objects, layout.squares, spec.marker_size)

    # Create black squares (Blender-specific)
    return _create_black_squares(spec, center)


def create_aprilgrid_layout(
    tag_objects: list[MeshObject],
    *,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    corner_size: float = 0.02,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int | None = None,
    rows: int | None = None,
) -> list[MeshObject]:
    """Position tags in a Kalibr AprilGrid pattern.

    Tags are placed in every cell with black corner squares at intersections.

    Args:
        tag_objects: List of tag mesh objects to position.
        square_size: Size of each grid cell (meters).
        marker_margin: Margin between marker edge and cell edge.
        corner_size: Size of corner squares (meters).
        center: Center point of the board.
        cols: Number of columns (auto-calculated if None).
        rows: Number of rows (auto-calculated if None).

    Returns:
        List of created corner square objects.
    """
    n = len(tag_objects)
    if n == 0:
        return []

    # Auto-calculate grid size if not provided
    if cols is None or rows is None:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

    # Use tested geometry module for positions
    spec = BoardSpec(
        rows=rows,
        cols=cols,
        square_size=square_size,
        marker_margin=marker_margin,
        board_type=BoardType.APRILGRID,
    )
    layout = compute_aprilgrid_layout(spec, corner_size=corner_size, center=center)

    # Apply positions to Blender objects
    _apply_tag_positions(tag_objects, layout.squares, spec.marker_size)

    # Create corner squares (Blender-specific)
    corner_positions = [(p.x, p.y, p.z) for p in layout.corner_positions]
    return _create_corner_squares(corner_positions, corner_size)


# =============================================================================
# Internal Helpers (Blender-specific)
# =============================================================================


def _apply_tag_positions(
    tag_objects: list[MeshObject],
    squares: list,
    marker_size: float,
) -> None:
    """Apply computed positions to Blender tag objects."""
    tag_idx = 0
    for sq in squares:
        if sq.has_tag and tag_idx < len(tag_objects):
            tag = tag_objects[tag_idx]
            tag.set_location([sq.center.x, sq.center.y, sq.center.z])
            tag.set_rotation_euler([0, 0, 0])

            # Scale tag to fit within square
            current_size = max(tag.blender_obj.dimensions[:2])
            if current_size > 0:
                scale = marker_size / current_size
                tag.set_scale([scale, scale, 1])
                tag.persist_transformation_into_mesh()

            tag_idx += 1


def _create_black_squares(
    spec: BoardSpec,
    center: tuple[float, float, float],
) -> list[MeshObject]:
    """Create black squares for ChArUco board."""
    start_x = center[0] - spec.board_width / 2 + spec.square_size / 2
    start_y = center[1] - spec.board_height / 2 + spec.square_size / 2

    squares = []
    for row in range(spec.rows):
        for col in range(spec.cols):
            # Black squares are (row+col) % 2 == 1
            if (row + col) % 2 != 1:
                continue

            x = start_x + col * spec.square_size
            y = start_y + row * spec.square_size
            z = center[2] - 0.0001  # Slightly below tags

            square = bproc.object.create_primitive("PLANE")
            square.set_location([x, y, z])
            square.set_scale([spec.square_size / 2, spec.square_size / 2, 1])
            square.persist_transformation_into_mesh()

            # Apply black material
            mat = _create_black_material(f"BlackSquare_{row}_{col}")
            square.blender_obj.data.materials.clear()
            square.blender_obj.data.materials.append(mat)

            squares.append(square)

    return squares


def _create_corner_squares(
    positions: list[tuple[float, float, float]],
    size: float,
) -> list[MeshObject]:
    """Create black corner squares at given positions."""
    corners = []
    for i, (x, y, z) in enumerate(positions):
        corner = bproc.object.create_primitive("PLANE")
        corner.set_location([x, y, z])
        corner.set_scale([size / 2, size / 2, 1])
        corner.persist_transformation_into_mesh()

        mat = _create_black_material(f"CornerBlack_{i}")
        corner.blender_obj.data.materials.clear()
        corner.blender_obj.data.materials.append(mat)

        corners.append(corner)

    return corners


def _create_black_material(name: str) -> bpy.types.Material:
    """Create a simple black material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
        bsdf.inputs["Roughness"].default_value = 1.0

    return mat
