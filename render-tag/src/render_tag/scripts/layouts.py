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
    corner_size: float = 0.01,
    center: tuple[float, float, float] = (0, 0, 0),
) -> list:
    """Position tags with black corner squares linking them in a grid.
    
    Creates a calibration board-like layout where tags are connected
    at their corners by small black squares.
    
    Args:
        tag_objects: List of tag mesh objects to position
        corner_size: Size of black corner squares in meters
        center: Center point of the board
        
    Returns:
        List of created corner square objects
    """
    n = len(tag_objects)
    if n == 0:
        return []
    
    # Calculate grid dimensions
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    
    # Get tag size from first tag
    if tag_objects:
        tag_size = max(tag_objects[0].blender_obj.dimensions[:2])
    else:
        tag_size = 0.1
    
    # Spacing = tag size + corner size (corners touch tag edges)
    spacing = tag_size + corner_size
    
    # Calculate starting position
    grid_width = (cols - 1) * spacing
    grid_height = (rows - 1) * spacing
    start_x = center[0] - grid_width / 2
    start_y = center[1] - grid_height / 2
    
    # Position tags
    for i, tag in enumerate(tag_objects):
        col = i % cols
        row = i // cols
        
        x = start_x + col * spacing
        y = start_y + row * spacing
        z = center[2]
        
        tag.set_location([x, y, z])
        tag.set_rotation_euler([0, 0, 0])  # No rotation for calibration board
    
    # Create corner squares at intersections
    corner_positions = _compute_corner_positions(
        cols=cols,
        rows=rows,
        tag_size=tag_size,
        corner_size=corner_size,
        start_x=start_x,
        start_y=start_y,
        z=center[2],
    )
    
    corner_objects = create_corner_squares(corner_positions, corner_size)
    return corner_objects


def _compute_corner_positions(
    cols: int,
    rows: int,
    tag_size: float,
    corner_size: float,
    start_x: float,
    start_y: float,
    z: float,
) -> list[tuple[float, float, float]]:
    """Compute positions for black corner squares.
    
    Corners are placed at the intersection points between tags.
    """
    positions = []
    spacing = tag_size + corner_size
    half_tag = tag_size / 2
    half_corner = corner_size / 2
    
    for row in range(rows):
        for col in range(cols):
            tag_x = start_x + col * spacing
            tag_y = start_y + row * spacing
            
            # Add corners at each corner of the tag
            # Only add if there's an adjacent tag to connect to
            
            # Top-right corner (connects to right and top neighbour)
            if col < cols - 1 or row < rows - 1:
                corner_x = tag_x + half_tag + half_corner
                corner_y = tag_y + half_tag + half_corner
                if (corner_x, corner_y, z) not in positions:
                    positions.append((corner_x, corner_y, z))
            
            # Top-left corner
            if col > 0 or row < rows - 1:
                corner_x = tag_x - half_tag - half_corner
                corner_y = tag_y + half_tag + half_corner
                if (corner_x, corner_y, z) not in positions:
                    positions.append((corner_x, corner_y, z))
            
            # Bottom-right corner
            if col < cols - 1 or row > 0:
                corner_x = tag_x + half_tag + half_corner
                corner_y = tag_y - half_tag - half_corner
                if (corner_x, corner_y, z) not in positions:
                    positions.append((corner_x, corner_y, z))
            
            # Bottom-left corner
            if col > 0 or row > 0:
                corner_x = tag_x - half_tag - half_corner
                corner_y = tag_y - half_tag - half_corner
                if (corner_x, corner_y, z) not in positions:
                    positions.append((corner_x, corner_y, z))
    
    return positions


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
    corner_size: float = 0.01,
    center: tuple[float, float, float] = (0, 0, 0),
) -> list:
    """Apply the specified layout to tag objects.
    
    Args:
        tag_objects: List of tag mesh objects
        layout_mode: "plain" or "cb" (checkerboard)
        spacing: Tag spacing for plain layout
        corner_size: Corner size for checkerboard layout
        center: Center point of the layout
        
    Returns:
        List of additional objects created (corner squares for checkerboard)
    """
    if layout_mode == "plain":
        create_plain_layout(tag_objects, spacing, center)
        return []
    elif layout_mode == "cb":
        return create_checkerboard_layout(tag_objects, corner_size, center)
    else:
        # Default to plain
        create_plain_layout(tag_objects, spacing, center)
        return []
