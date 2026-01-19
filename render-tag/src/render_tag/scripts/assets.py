"""
Asset loading utilities for render-tag.

This module handles creating tag planes with proper texturing and corner tracking.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import blenderproc as bproc

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
    import mathutils
    import numpy as np
except ImportError:
    bproc = None  # type: ignore
    bpy = None  # type: ignore
    mathutils = None  # type: ignore
    np = None  # type: ignore


# Corner order: Counter-Clockwise from Bottom-Left
# BL (0), BR (1), TR (2), TL (3)
CORNER_ORDER = [
    (-0.5, -0.5, 0),  # Bottom-Left
    (0.5, -0.5, 0),   # Bottom-Right
    (0.5, 0.5, 0),    # Top-Right
    (-0.5, 0.5, 0),   # Top-Left
]


def get_tag_texture_path(
    tag_family: str, 
    custom_path: Optional[Path] = None,
    tag_id: Optional[int] = None,
) -> Optional[Path]:
    """Get the path to a tag texture file.
    
    Args:
        tag_family: The tag family identifier (e.g., "tag36h11", "DICT_4X4_50")
        custom_path: Optional custom texture path
        tag_id: Optional marker ID for indexed textures (e.g., "tag36h11_0.png")
        
    Returns:
        Path to the texture file, or None if not found
    """
    if custom_path and Path(custom_path).exists():
        return Path(custom_path)
    
    # Check for specific indexed tag first
    if tag_id is not None:
        indexed_paths = [
            Path("assets/tags") / f"{tag_family}_{tag_id}.png",
            Path("assets/textures") / f"{tag_family}_{tag_id}.png",
        ]
        for path in indexed_paths:
            if path.exists():
                return path

    # Default texture locations
    default_paths = [
        Path("assets/textures") / f"{tag_family}.png",
        Path("assets/tags") / f"{tag_family}.png",
    ]
    
    for path in default_paths:
        if path.exists():
            return path
    
    return None


def create_tag_plane(
    size_meters: float,
    texture_path: Optional[Path],
    tag_family: str,
    tag_id: int = 0,
) -> Any:
    """Create a textured plane representing a fiducial marker.
    
    Args:
        size_meters: The size of the tag in meters (outer edge)
        texture_path: Path to the tag texture image
        tag_family: Tag family identifier for metadata
        tag_id: Tag ID number
        
    Returns:
        BlenderProc MeshObject with corner coordinates stored as custom properties
    """
    # Create a plane primitive
    plane = bproc.object.create_primitive("PLANE")
    
    # Scale to desired size
    plane.set_scale([size_meters, size_meters, 1])
    
    # Apply the scale to make it permanent
    plane.persist_transformation_into_mesh()
    
    # Store corner coordinates as custom properties
    # These are in LOCAL space, scaled by size_meters
    corners_local = []
    for corner in CORNER_ORDER:
        corners_local.append([
            corner[0] * size_meters,
            corner[1] * size_meters,
            corner[2],
        ])
    
    # Store metadata on the object
    plane.blender_obj["corner_coords"] = corners_local
    plane.blender_obj["tag_id"] = tag_id
    plane.blender_obj["tag_family"] = tag_family
    
    # Apply texture if provided
    if texture_path and texture_path.exists():
        apply_tag_texture(plane, texture_path)
    else:
        # Apply a default material (white with slight roughness)
        apply_default_material(plane)
    
    return plane


def apply_tag_texture(obj: Any, texture_path: Path) -> None:
    """Apply a texture to the tag plane with correct UV mapping.
    
    Args:
        obj: The BlenderProc mesh object
        texture_path: Path to the texture image
    """
    # Load the texture image
    image = bpy.data.images.load(str(texture_path))
    
    # Create a new material
    material = bpy.data.materials.new(name=f"TagMaterial_{texture_path.stem}")
    material.use_nodes = True
    
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    output_node = nodes.new("ShaderNodeOutputMaterial")
    bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
    tex_node = nodes.new("ShaderNodeTexImage")
    
    # Set texture
    tex_node.image = image
    tex_node.interpolation = "Closest"  # Sharp pixels for tags
    
    # Set material properties for a printed tag
    bsdf_node.inputs["Roughness"].default_value = 0.8
    bsdf_node.inputs["Specular IOR Level"].default_value = 0.2
    
    # Link nodes
    links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])
    
    # Assign material to object
    obj.blender_obj.data.materials.clear()
    obj.blender_obj.data.materials.append(material)


def apply_default_material(obj: Any) -> None:
    """Apply a default white material to the tag.
    
    Args:
        obj: The BlenderProc mesh object
    """
    material = bpy.data.materials.new(name="TagMaterial_Default")
    material.use_nodes = True
    
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Roughness"].default_value = 0.8
    
    obj.blender_obj.data.materials.clear()
    obj.blender_obj.data.materials.append(material)


def get_corner_world_coords(tag_obj: Any) -> list[list[float]]:
    """Get the world coordinates of the tag corners.
    
    Args:
        tag_obj: The tag mesh object
        
    Returns:
        List of 4 corner coordinates in world space [x, y, z]
    """
    # Get local corner coordinates from custom property
    corners_local = tag_obj.blender_obj.get("corner_coords", [])
    
    if not corners_local:
        # Fallback: compute from default corners
        size = max(tag_obj.blender_obj.dimensions[:2])
        corners_local = [
            [c[0] * size, c[1] * size, c[2]] for c in CORNER_ORDER
        ]
    
    world_matrix = tag_obj.get_local2world_mat()
    corners_world = []
    for corner in corners_local:
        # Transform each corner to world space using the 4x4 matrix
        local_pos = np.array(corner[:3])
        # Homogeneous coordinates trick: add 1.0 and dot with 4x4 matrix
        local_homo = np.append(local_pos, 1.0)
        world_homo = np.dot(world_matrix, local_homo)
        
        # Project back to 3D by dividing by w (usually 1.0 for affine transforms)
        if abs(world_homo[3]) > 1e-6:
            world_pos = world_homo[:3] / world_homo[3]
        else:
            world_pos = world_homo[:3]
            
        corners_world.append(world_pos.tolist())
    
    return corners_world
