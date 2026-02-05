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
from typing import TYPE_CHECKING

from render_tag.backend.bridge import bproc, bpy
from render_tag.geometry.board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
)

if TYPE_CHECKING:
    from typing import Any
    MeshObject = Any


# =============================================================================
# Public API
# =============================================================================


def apply_layout(
    tag_objects: list[MeshObject],
    layout_mode: str,
    *,
    spacing: float = 0.05,
    tag_size: float = 0.1,
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
        spacing: Gap between tag edges for plain layout (meters).
        tag_size: Size of each tag (meters) - used for plain layout.
        square_size: Size of each grid cell for CB/AprilGrid (meters).
        marker_margin: Margin between marker and cell edge (meters).
        corner_size: Size of corner squares for AprilGrid (meters).
        center: Center point of the layout.
        cols: Number of columns (auto-calculated if None).
        rows: Number of rows (auto-calculated if None).

    Returns:
        List of additional objects created (black squares, corners).
    """
    if layout_mode == "plain":
        create_plain_layout(tag_objects, spacing=spacing, tag_size=tag_size, center=center)
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
    tag_size: float = 0.1,
    center: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """Position tags in a grid layout.

    Args:
        tag_objects: List of tag mesh objects to position.
        spacing: Gap between tag edges (white space) in meters.
        tag_size: Size of each tag in meters.
        center: Center point of the grid.
    """
    n = len(tag_objects)
    if n == 0:
        return

    # Center-to-center distance = tag_size + gap
    cell_size = tag_size + spacing

    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    grid_width = (cols - 1) * cell_size
    grid_height = (rows - 1) * cell_size
    start_x = center[0] - grid_width / 2
    start_y = center[1] - grid_height / 2

    for i, tag in enumerate(tag_objects):
        col, row = i % cols, i // cols
        x = start_x + col * cell_size
        y = start_y + row * cell_size

        tag.set_location([x, y, center[2]])
        tag.set_rotation_euler([0, 0, 0])


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
            square.blender_obj.name = f"Layout_Square_{row}_{col}"
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
        corner.blender_obj.name = f"Layout_Corner_{i}"
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
    mat.diffuse_color = (0, 0, 0, 1)  # Viewport color for Workbench
    mat.use_nodes = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
        bsdf.inputs["Roughness"].default_value = 1.0

    return mat
