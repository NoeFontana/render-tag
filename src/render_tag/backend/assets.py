"""
Asset loading utilities for render-tag.

This module handles creating tag planes with proper texturing and corner tracking.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import bpy
except ImportError:
    bpy = None

from render_tag.backend.bridge import bridge

if TYPE_CHECKING:
    pass


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
        self._bg_plane: Any | None = None

    def get_tag(self) -> Any:
        """Get an available tag plane from the pool or create a new one."""
        if self._active_count < len(self._tag_pool):
            obj = self._tag_pool[self._active_count]
            obj.blender_obj.hide_render = False
            obj.blender_obj.hide_viewport = False
        else:
            # Create a new plane primitive
            obj = bridge.bproc.object.create_primitive("PLANE")
            self._tag_pool.append(obj)

        self._active_count += 1
        return obj

    def get_background_plane(self) -> Any:
        """Get or create the singleton background plane."""
        if self._bg_plane is None:
            self._bg_plane = bridge.bproc.object.create_primitive("PLANE")
            self._bg_plane.blender_obj.name = "Background_Plane_Persistent"
            # Initial setup
            self._bg_plane.set_scale([20, 20, 1])
            self._bg_plane.set_location([0, 0, -0.01])
            self._bg_plane.persist_transformation_into_mesh()

        self._bg_plane.blender_obj.hide_render = False
        self._bg_plane.blender_obj.hide_viewport = False
        return self._bg_plane

    def release_all(self):
        """Reset the pool, hiding all objects for the next scene."""
        for obj in self._tag_pool:
            obj.blender_obj.hide_render = True
            obj.blender_obj.hide_viewport = True
            # Reset transforms to avoid state leak
            obj.set_location([0, 0, 0])
            obj.set_scale([1, 1, 1])
            # Reset parent if any
            obj.blender_obj.parent = None

        if self._bg_plane:
            self._bg_plane.blender_obj.hide_render = True
            self._bg_plane.blender_obj.hide_viewport = True

        self._active_count = 0


# Global singleton for the backend session
global_pool = AssetPool()


def get_tag_texture_path(
    tag_family: str,
    custom_path: Path | None = None,
    tag_id: int | None = None,
    margin_bits: int = 0,
) -> Path | None:
    """Get the path to a tag texture file.

    Args:
        tag_family: The tag family identifier (e.g., "tag36h11", "DICT_4X4_50")
        custom_path: Optional custom texture path
        tag_id: Optional marker ID for indexed textures (e.g., "tag36h11_0.png")
        margin_bits: Quiet zone width suffix

    Returns:
        Path to the texture file, or None if not found
    """
    if custom_path and Path(custom_path).exists():
        return Path(custom_path)

    # Check for specific indexed tag first
    if tag_id is not None:
        indexed_paths = [
            Path("assets/tags") / f"{tag_family}_{tag_id}_m{margin_bits}.png",
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
    margin_bits: int = 0,
) -> Any:
    """Create a textured plane representing a fiducial marker.

    Args:
        size_meters: The size of the tag in meters (outer edge, including margin)
        texture_path: Path to the tag texture image
        tag_family: Tag family identifier for metadata
        tag_id: Tag ID number
        material_config: Dict for randomization
        margin_bits: Quiet zone width in bits

    Returns:
        BlenderProc MeshObject with corner coordinates stored as custom properties
    """
    # Retrieve from pool instead of creating new
    plane = global_pool.get_tag()
    plane.blender_obj.name = f"Tag_{tag_family}_{tag_id}"

    # Scale to desired size
    # PLANE primitive is 2x2 (-1 to 1), so we scale by size/2
    plane.set_scale([size_meters / 2.0, size_meters / 2.0, 1])

    # Store corner coordinates as custom properties
    # Detection standard is the OUTER BLACK BORDER corners.
    # If margin_bits > 0, the black border is smaller than size_meters.
    from render_tag.core import TAG_GRID_SIZES

    grid_size = TAG_GRID_SIZES.get(tag_family, 8)
    total_bits = grid_size + (2 * margin_bits)

    # Calculate scale factor for black border relative to total plane
    black_border_scale = grid_size / total_bits
    half_black = (size_meters * black_border_scale) / 2.0

    corners_local = [
        [-half_black, -half_black, 0.0],  # BL
        [half_black, -half_black, 0.0],  # BR
        [half_black, half_black, 0.0],  # TR
        [-half_black, half_black, 0.0],  # TL
    ]

    # Store metadata on the object
    plane.blender_obj["corner_coords"] = corners_local
    plane.blender_obj["tag_id"] = tag_id
    plane.blender_obj["tag_family"] = tag_family
    plane.blender_obj["margin_bits"] = margin_bits

    # Apply texture if provided
    if texture_path and texture_path.exists():
        apply_tag_texture(plane, texture_path, material_config)
    else:
        # Apply a default material (white with slight roughness)
        apply_default_material(plane)

    # Disable shadow casting to avoid "floating" look for stickers
    plane.blender_obj.visible_shadow = False

    return plane


def apply_tag_texture(obj: Any, texture_path: Path, config: dict | None = None) -> None:
    """Apply a texture to the tag plane with correct UV mapping.

    Args:
        obj: The BlenderProc mesh object
        texture_path: Path to the texture image
        config: Material configuration dictionary
    """
    # Load the texture image
    # Check if already loaded
    img_name = texture_path.name
    image = bridge.bpy.data.images.get(img_name)
    if not image:
        try:
            image = bridge.bpy.data.images.load(str(texture_path))
        except RuntimeError:
            # Fallback if load fails
            return

    # Reuse or create material
    mat_name = "TagMaterial_Pooled"
    material = bridge.bpy.data.materials.get(mat_name)
    if not material:
        material = bridge.bpy.data.materials.new(name=mat_name)
        material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Find or create nodes
    output_node = nodes.get("Material Output") or nodes.new("ShaderNodeOutputMaterial")
    bsdf_node = nodes.get("Principled BSDF") or nodes.new("ShaderNodeBsdfPrincipled")
    tex_node = nodes.get("Image Texture") or nodes.new("ShaderNodeTexImage")
    tex_node.name = "Image Texture"  # Ensure we can find it next time

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
    if not any(link.to_node == bsdf_node and link.to_socket.name == "Base Color" for link in links):
        links.new(tex_node.outputs["Color"], bsdf_node.inputs["Base Color"])
    if not any(link.to_node == bsdf_node and link.to_socket.name == "Alpha" for link in links):
        links.new(tex_node.outputs["Alpha"], bsdf_node.inputs["Alpha"])
    if not any(link.to_node == output_node for link in links):
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
    material = bridge.bpy.data.materials.new(name="TagMaterial_Default")
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
        local_pos = bridge.np.array(corner[:3])
        # Homogeneous coordinates trick: add 1.0 and dot with 4x4 matrix
        local_homo = bridge.np.append(local_pos, 1.0)
        world_homo = bridge.np.dot(world_matrix, local_homo)

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
