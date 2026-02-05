"""
Asset loading utilities for render-tag.

This module handles creating tag planes with proper texturing and corner tracking.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import blenderproc as bproc

try:
    import numpy as np
except ImportError:
    np = None

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
    import mathutils
except (ImportError, RuntimeError):
    bproc = None  # type: ignore
    bpy = None  # type: ignore
    mathutils = None  # type: ignore

def setup_mocks(bproc_mock, bpy_mock):
    """Inject mocks for testing."""
    global bproc, bpy
    bproc = bproc_mock
    bpy = bpy_mock


# Corner order: Counter-Clockwise from Bottom-Left
# BL (0), BR (1), TR (2), TL (3)
CORNER_ORDER = [
    (-0.5, -0.5, 0),  # Bottom-Left
    (0.5, -0.5, 0),  # Bottom-Right
    (0.5, 0.5, 0),  # Top-Right
    (-0.5, 0.5, 0),  # Top-Left
]


class AssetPool:
    """Manages a pool of Blender objects to avoid creation/deletion overhead."""

    def __init__(self):
        self._tag_pool: list[Any] = []
        self._active_count = 0

    def get_tag(self) -> Any:
        """Get an available tag plane from the pool or create a new one."""
        if self._active_count < len(self._tag_pool):
            obj = self._tag_pool[self._active_count]
            obj.blender_obj.hide_render = False
            obj.blender_obj.hide_viewport = False
        else:
            # Create a new plane primitive
            obj = bproc.object.create_primitive("PLANE")
            self._tag_pool.append(obj)

        self._active_count += 1
        return obj

    def release_all(self):
        """Reset the pool, hiding all objects for the next scene."""
        for obj in self._tag_pool:
            obj.blender_obj.hide_render = True
            obj.blender_obj.hide_viewport = True
            # Reset parent if any
            obj.blender_obj.parent = None
        self._active_count = 0


# Global singleton for the backend session
global_pool = AssetPool()


def get_tag_texture_path(
    tag_family: str,
    custom_path: Path | None = None,
    tag_id: int | None = None,
) -> Path | None:
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
        Path("assets/textures/background/adversarial") / f"{tag_family}.png",
        Path("assets/textures/background/natural") / f"{tag_family}.png",
        Path("assets/textures") / f"{tag_family}.png",
        Path("assets/tags") / f"{tag_family}.png",
    ]

    for path in default_paths:
        if path.exists():
            return path

    return None


def create_tag_plane(
    size_meters: float,
    texture_path: Path | None,
    tag_family: str,
    tag_id: int = 0,
    material_config: dict | None = None,
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
    # Retrieve from pool instead of creating new
    plane = global_pool.get_tag()
    plane.blender_obj.name = f"Tag_{tag_family}_{tag_id}"

    # Scale to desired size
    # PLANE primitive is 2x2 (-1 to 1), so we scale by size/2
    plane.set_scale([size_meters / 2.0, size_meters / 2.0, 1])

    # Apply the scale to make it permanent
    plane.persist_transformation_into_mesh()

    # Store corner coordinates as custom properties
    # After persist_transformation_into_mesh, the mesh is already scaled.
    # So we use base corners (half size) without additional scaling.
    # These will be transformed to world space via matrix_world.
    half = size_meters / 2.0
    corners_local = [
        [-half, -half, 0.0],  # BL
        [half, -half, 0.0],  # BR
        [half, half, 0.0],  # TR
        [-half, half, 0.0],  # TL
    ]

    # Store metadata on the object
    plane.blender_obj["corner_coords"] = corners_local
    plane.blender_obj["tag_id"] = tag_id
    plane.blender_obj["tag_family"] = tag_family

    # Apply texture if provided
    if texture_path and texture_path.exists():
        apply_tag_texture(plane, texture_path, material_config)
    else:
        # Apply a default material (white with slight roughness)
        apply_default_material(plane)

    return plane


def apply_tag_texture(obj: Any, texture_path: Path, config: dict | None = None) -> None:
    """Apply a texture to the tag plane with correct UV mapping.

    Args:
        obj: The BlenderProc mesh object
        texture_path: Path to the texture image
        config: Material configuration dictionary
    """
    # Load the texture image
    image = bpy.data.images.load(str(texture_path))

    # Reuse or create material
    mat_name = f"TagMaterial_Pooled"
    material = bpy.data.materials.get(mat_name)
    if not material:
        material = bpy.data.materials.new(name=mat_name)
        material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Find or create nodes
    output_node = nodes.get("Material Output") or nodes.new("ShaderNodeOutputMaterial")
    bsdf_node = nodes.get("Principled BSDF") or nodes.new("ShaderNodeBsdfPrincipled")
    tex_node = nodes.get("Image Texture") or nodes.new("ShaderNodeTexImage")
    tex_node.name = "Image Texture" # Ensure we can find it next time

    # Set texture
    tex_node.image = image
    tex_node.interpolation = "Closest"  # Sharp pixels for tags

    # Set material properties for a printed tag
    # Defaults (Backward Compatibility for existing hardcoded values)
    roughness = 0.8
    specular = 0.2

    if config and config.get("randomize", False):
        # Sample from configured ranges
        roughness = random.uniform(
            config.get("roughness_min", 0.6), config.get("roughness_max", 1.0)
        )
        specular = random.uniform(config.get("specular_min", 0.1), config.get("specular_max", 0.3))

    bsdf_node.inputs["Roughness"].default_value = roughness
    bsdf_node.inputs["Specular IOR Level"].default_value = specular

    # Link nodes if not already linked
    if not any(l.to_node == bsdf_node and l.to_socket.name == "Base Color" for l in links):
        links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    if not any(l.to_node == output_node for l in links):
        links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

    # Assign material to object (clearing existing ones first)
    if not obj.blender_obj.data.materials or obj.blender_obj.data.materials[0] != material:
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
        corners_local = [[c[0] * size, c[1] * size, c[2]] for c in CORNER_ORDER]

    world_matrix = tag_obj.get_local2world_mat()
    corners_world = []
    for corner in corners_local:
        # Transform each corner to world space using the 4x4 matrix
        local_pos = np.array(corner[:3])
        # Homogeneous coordinates trick: add 1.0 and dot with 4x4 matrix
        local_homo = np.append(local_pos, 1.0)
        world_homo = np.dot(world_matrix, local_homo)

        # Project back to 3D by dividing by w (usually 1.0 for affine transforms)
        world_pos = world_homo[:3] / world_homo[3] if abs(world_homo[3]) > 1e-6 else world_homo[:3]

        corners_world.append(world_pos.tolist())

    return corners_world


def apply_surface_imperfections(
    obj: Any,
    scratches: float = 0.0,
    dust: float = 0.0,
    grunge: float = 0.0,
) -> None:
    """Apply procedural surface imperfections to the object's material.

    Args:
        obj: BlenderProc mesh object
        scratches: Intensity of scratches (0-1)
        dust: Intensity of dust (0-1)
        grunge: Intensity of grunge (0-1)
    """
    if not (scratches > 0 or dust > 0 or grunge > 0):
        return

    # Check for material
    if not obj.blender_obj.data.materials:
        return

    mat = obj.blender_obj.data.materials[0]
    if not mat.use_nodes:
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Find Principled BSDF
    # Note: In Blender 4.0+ it might be named differently, but "Principled BSDF" is standard
    # We iterate to find type 'BSDF_PRINCIPLED'
    bsdf = None
    for node in nodes:
        if node.type == "BSDF_PRINCIPLED":
            bsdf = node
            break

    if not bsdf:
        return

    # Implementation:
    # We use Noise and Musgrave textures to perturb Roughness and Color

    # 1. Scratches (Roughness)
    if scratches > 0 and bpy:
        # Create Scratch Noise
        scratch_tex = nodes.new("ShaderNodeTexNoise")
        scratch_tex.inputs["Scale"].default_value = 50.0
        scratch_tex.inputs["Detail"].default_value = 10.0
        scratch_tex.inputs["Roughness"].default_value = 0.6
        scratch_tex.inputs["Distortion"].default_value = 2.0

        # ColorRamp to sharpen scratches
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.4
        ramp.color_ramp.elements[1].position = 0.6
        links.new(scratch_tex.outputs["Fac"], ramp.inputs["Fac"])

        # Mix with current roughness
        # We need a Mix Node. In older Blender it's MixRGB, newer is Mix
        try:
            mix = nodes.new("ShaderNodeMix")
            mix.data_type = "FLOAT"
            mix.inputs["Factor"].default_value = scratches
            # If nothing connected to roughness, get default
            current_roughness = bsdf.inputs["Roughness"].default_value
            mix.inputs[4].default_value = current_roughness  # A
            links.new(ramp.outputs["Alpha"], mix.inputs[5])  # B (using alpha as value)
            links.new(mix.outputs[0], bsdf.inputs["Roughness"])
        except Exception:
            # Fallback for older Blender versions (MixRGB)
            pass

    # 2. Dust (Color overlay)
    # Placeholder logic
    pass