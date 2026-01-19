"""
Layout generators for render-tag scene composition.

This module handles positioning tags in different layout modes:
- Plain: Tags equidistant from each other, no connecting elements
- Checkerboard: Tags connected by black corner squares in a grid
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
    import numpy as np
except ImportError:
    bproc = None  # type: ignore
    bpy = None  # type: ignore
    np = None  # type: ignore


def create_plain_layout(
    tag_objects: list,
    spacing: float = 0.05,
    center: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """Position tags equidistant in a grid with no connecting elements.
    
    Tags are arranged in a grid pattern with uniform spacing.
    
    Args:
        tag_objects: List of tag mesh objects to position
        spacing: Distance between tag centers in meters
        center: Center point of the grid
    """
    n = len(tag_objects)
    if n == 0:
        return
    
    # Calculate grid dimensions (roughly square)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    
    # Calculate starting position for centered grid
    grid_width = (cols - 1) * spacing
    grid_height = (rows - 1) * spacing
    start_x = center[0] - grid_width / 2
    start_y = center[1] - grid_height / 2
    
    for i, tag in enumerate(tag_objects):
        col = i % cols
        row = i // cols
        
        x = start_x + col * spacing
        y = start_y + row * spacing
        z = center[2]
        
        tag.set_location([x, y, z])
        # Tags lie flat on ground, facing up
        tag.set_rotation_euler([0, 0, random.uniform(0, 2 * np.pi)])


def create_checkerboard_layout(
    tag_objects: list,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int = None,
    rows: int = None,
) -> list:
    """Position tags in a ChArUco board pattern.
    
    Creates a calibration board where tags are placed in the 'white' squares
    of a checkerboard pattern. Black squares fill the alternating positions.
    This matches the OpenCV cv::aruco::CharucoBoard layout.
    
    Args:
        tag_objects: List of tag mesh objects to position
        square_size: Size of each checkerboard square in meters
        marker_margin: Margin between marker edge and square edge
        center: Center point of the board
        cols: Number of columns in the checkerboard (total squares)
        rows: Number of rows in the checkerboard (total squares)
        
    Returns:
        List of created black square objects
    """
    n = len(tag_objects)
    if n == 0:
        return []
    
    # Calculate grid dimensions based on number of tags
    # In a ChArUco board, tags only go in white squares (alternating)
    # For an MxN board, there are ceil(M*N/2) white squares
    if cols is None or rows is None:
        # Estimate grid size to fit n tags in alternating pattern
        # For a square-ish board: cols*rows/2 >= n
        total_squares = n * 2  # Roughly
        cols = int(np.ceil(np.sqrt(total_squares)))
        rows = int(np.ceil(total_squares / cols))
    
    # Calculate board dimensions
    board_width = cols * square_size
    board_height = rows * square_size
    
    # Calculate starting position (bottom-left corner of the board)
    start_x = center[0] - board_width / 2 + square_size / 2
    start_y = center[1] - board_height / 2 + square_size / 2
    
    # Determine which squares are "white" (where tags go)
    # In a standard checkerboard, (row+col) % 2 == 0 is one color
    # We'll put tags in (row+col) % 2 == 0 positions
    tag_idx = 0
    marker_size = square_size - 2 * marker_margin  # Marker fits inside square
    
    for row in range(rows):
        for col in range(cols):
            x = start_x + col * square_size
            y = start_y + row * square_size
            z = center[2]
            
            is_white_square = (row + col) % 2 == 0
            
            if is_white_square and tag_idx < n:
                # Place tag in this white square
                tag = tag_objects[tag_idx]
                tag.set_location([x, y, z])
                tag.set_rotation_euler([0, 0, 0])
                
                # Scale tag to fit within the square (accounting for margin)
                current_size = max(tag.blender_obj.dimensions[:2])
                if current_size > 0:
                    scale_factor = marker_size / current_size
                    tag.set_scale([scale_factor, scale_factor, 1])
                    tag.persist_transformation_into_mesh()
                
                tag_idx += 1
    
    # Create black squares in the alternating positions
    black_squares = []
    for row in range(rows):
        for col in range(cols):
            x = start_x + col * square_size
            y = start_y + row * square_size
            z = center[2] - 0.0001  # Slightly below tags
            
            is_black_square = (row + col) % 2 == 1
            
            if is_black_square:
                # Create a black square
                square = bproc.object.create_primitive("PLANE")
                square.set_location([x, y, z])
                square.set_scale([square_size / 2, square_size / 2, 1])
                square.persist_transformation_into_mesh()
                
                # Apply black material
                mat = bpy.data.materials.new(name=f"BlackSquare_{row}_{col}")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
                    bsdf.inputs["Roughness"].default_value = 1.0
                
                square.blender_obj.data.materials.clear()
                square.blender_obj.data.materials.append(mat)
                
                black_squares.append(square)
    
    return black_squares


def create_corner_squares(
    positions: list[tuple[float, float, float]],
    size: float,
) -> list:
    """Create black corner squares at the given positions.
    
    Args:
        positions: List of (x, y, z) positions for corners
        size: Size of each square in meters
        
    Returns:
        List of created corner mesh objects
    """
    corners = []
    
    for i, pos in enumerate(positions):
        # Create a small plane for the corner
        corner = bproc.object.create_primitive("PLANE")
        corner.set_location(list(pos))
        corner.set_scale([size / 2, size / 2, 1])  # Plane is 2x2 by default
        corner.persist_transformation_into_mesh()
        
        # Apply black material
        material = bpy.data.materials.new(name=f"CornerBlack_{i}")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
            bsdf.inputs["Roughness"].default_value = 1.0
        
        corner.blender_obj.data.materials.clear()
        corner.blender_obj.data.materials.append(material)
        
        corners.append(corner)
    
    return corners


def apply_layout(
    tag_objects: list,
    layout_mode: str,
    spacing: float = 0.05,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    corner_size: float = 0.02,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int = None,
    rows: int = None,
) -> list:
    """Apply the specified layout to tag objects.
    
    Args:
        tag_objects: List of tag mesh objects
        layout_mode: "plain", "cb" (charuco), or "aprilgrid" (kalibr)
        spacing: Tag spacing for plain layout
        square_size: Size of each checkerboard square (for cb mode)
        marker_margin: Margin between marker and square edge (for cb/aprilgrid)
        corner_size: Size of corner squares (for aprilgrid mode)
        center: Center point of the layout
        cols: Number of columns (for cb/aprilgrid mode)
        rows: Number of rows (for cb/aprilgrid mode)
        
    Returns:
        List of additional objects created (black squares for checkerboard)
    """
    if layout_mode == "plain":
        create_plain_layout(tag_objects, spacing, center)
        return []
    elif layout_mode == "cb":
        return create_checkerboard_layout(
            tag_objects, square_size, marker_margin, center, cols, rows
        )
    elif layout_mode == "aprilgrid":
        return create_aprilgrid_layout(
            tag_objects, square_size, marker_margin, corner_size, center, cols, rows
        )
    else:
        # Default to plain
        create_plain_layout(tag_objects, spacing, center)
        return []


def create_aprilgrid_layout(
    tag_objects: list,
    square_size: float = 0.12,
    marker_margin: float = 0.01,
    corner_size: float = 0.02,
    center: tuple[float, float, float] = (0, 0, 0),
    cols: int = None,
    rows: int = None,
) -> list:
    """Position tags in a Kalibr AprilGrid pattern.
    
    Creates a calibration board where tags are placed in every cell,
    with small black corner squares at the intersections.
    This matches the Kalibr AprilGrid format.
    
    Args:
        tag_objects: List of tag mesh objects to position
        square_size: Size of each grid cell in meters
        marker_margin: Margin between marker edge and cell edge
        corner_size: Size of the black corner squares
        center: Center point of the board
        cols: Number of columns in the grid
        rows: Number of rows in the grid
        
    Returns:
        List of created corner square objects
    """
    n = len(tag_objects)
    if n == 0:
        return []
    
    # Calculate grid dimensions if not provided
    if cols is None or rows is None:
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
    
    # Calculate board dimensions
    board_width = cols * square_size
    board_height = rows * square_size
    
    # Calculate starting position (center of bottom-left cell)
    start_x = center[0] - board_width / 2 + square_size / 2
    start_y = center[1] - board_height / 2 + square_size / 2
    
    # Place tags in every cell
    marker_size = square_size - 2 * marker_margin
    tag_idx = 0
    
    for row in range(rows):
        for col in range(cols):
            if tag_idx >= n:
                break
            
            x = start_x + col * square_size
            y = start_y + row * square_size
            z = center[2]
            
            tag = tag_objects[tag_idx]
            tag.set_location([x, y, z])
            tag.set_rotation_euler([0, 0, 0])
            
            # Scale tag to fit within the cell (accounting for margin)
            current_size = max(tag.blender_obj.dimensions[:2])
            if current_size > 0:
                scale_factor = marker_size / current_size
                tag.set_scale([scale_factor, scale_factor, 1])
                tag.persist_transformation_into_mesh()
            
            tag_idx += 1
    
    # Create corner squares at intersections (vertices of the grid)
    corner_positions = []
    
    # Vertices are at corners of cells, offset by half a cell from tag centers
    v_start = start_x - square_size / 2
    h_start = start_y - square_size / 2
    
    for r in range(rows + 1):
        for c in range(cols + 1):
            cx = v_start + c * square_size
            cy = h_start + r * square_size
            corner_positions.append((cx, cy, center[2]))
    
    corner_objects = create_corner_squares(corner_positions, corner_size)
    return corner_objects
