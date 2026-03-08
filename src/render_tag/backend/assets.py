"""
Asset loading utilities for render-tag.

This module handles creating tag planes with proper texturing and corner tracking.
All generated assets MUST adhere to the 3D-Anchored Orientation Contract:
1. Index 0 is Logical Top-Left.
2. Indices 1-3 follow a Clockwise winding in local 3D space.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import bpy
except ImportError:
    bpy = None

from render_tag.backend.bridge import bridge
from render_tag.core import TAG_GRID_SIZES

if TYPE_CHECKING:
    pass


# Corner order: Clockwise from Top-Left (Industry Standard)
# TL (0), TR (1), BR (2), BL (3)
# Note: Blender PLANE primitive is 2x2, so corners are at +/- 1.0 in local space.
CORNER_ORDER = [
    (-1.0, 1.0, 0),  # Top-Left
    (1.0, 1.0, 0),  # Top-Right
    (1.0, -1.0, 0),  # Bottom-Right
    (-1.0, -1.0, 0),  # Bottom-Left
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

    grid_size = TAG_GRID_SIZES.get(tag_family, 8)
    total_bits = grid_size + (2 * margin_bits)

    # Calculate local scale factor for black border relative to total plane.
    # Since the local plane is 2x2 (from -1 to 1), the half-width of the
    # full plane is 1.0. The half-width of the black border is thus:
    half_black = grid_size / total_bits

    corners_local = [
        [-half_black, half_black, 0.0],  # TL
        [half_black, half_black, 0.0],  # TR
        [half_black, -half_black, 0.0],  # BR
        [-half_black, -half_black, 0.0],  # BL
    ]

    # Store metadata on the object
    # Orientation Contract: keypoints_3d is the source of truth for ordered keypoints.
    plane.blender_obj["keypoints_3d"] = corners_local
    plane.blender_obj["tag_id"] = tag_id
    plane.blender_obj["tag_family"] = tag_family
    plane.blender_obj["margin_bits"] = margin_bits
    plane.blender_obj["raw_size_m"] = float(size_meters)

    # Apply texture if provided
    if texture_path:
        if texture_path.exists():
            apply_tag_texture(plane, texture_path, material_config)
        else:
            raise FileNotFoundError(f"Tag texture path provided but does not exist: {texture_path}")
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
        except RuntimeError as e:
            # Shift from silent return to explicit failure
            raise RuntimeError(
                f"Failed to load tag texture into Blender: {texture_path}. Error: {e}"
            ) from e

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
    # Move-Left: These are now resolved by the Compiler.
    roughness = 0.8
    specular = 0.2

    if config:
        # Use absolute values from recipe if present
        roughness = config.get("roughness", roughness)
        specular = config.get("specular", specular)

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

    Orientation Contract: Prefers 'keypoints_3d' (logical order).

    Args:
        tag_obj: The tag mesh object

    Returns:
        List of 4 corner coordinates in world space [x, y, z]
    """
    # 1. Get local corner coordinates from custom property
    # Prefer keypoints_3d (new contract) over corner_coords (legacy)
    corners_local = tag_obj.blender_obj.get("keypoints_3d")
    if not corners_local:
        corners_local = tag_obj.blender_obj.get("corner_coords", [])

    if not corners_local:
        # Fallback: use default corners in local space.
        # We distinguish between Unit Planes (TAG) and Physical Planes (BOARD).
        obj_type = tag_obj.blender_obj.get("type", "TAG")

        if obj_type == "BOARD":
            # Persisted board: dimensions reflect the physical size in meters.
            # Local space is already in meters, so we use dimensions/2.
            size_x, size_y = tag_obj.blender_obj.dimensions[:2]
            hx, hy = size_x / 2.0, size_y / 2.0
            corners_local = [[-hx, hy, 0.0], [hx, hy, 0.0], [hx, -hy, 0.0], [-hx, -hy, 0.0]]
        else:
            # Unit plane (TAG): world_matrix handles the local-to-world conversion
            # including scale, so we use normalized local corners here.
            corners_local = [list(c) for c in CORNER_ORDER]
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
