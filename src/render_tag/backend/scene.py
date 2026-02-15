"""
Scene construction utilities for render-tag.

This module handles background setup, lighting, floor creation, and physics.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from render_tag.backend.bridge import bridge

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def setup_background(hdri_path: Path) -> None:
    """Set the world background using an HDRI image.

    Implements lazy loading: only reloads if the path has changed.

    Args:
        hdri_path: Path to the HDRI image file (.exr or .hdr)
    """
    if not hdri_path.exists():
        logger.warning(f"HDRI path does not exist: {hdri_path}")
        return

    # Check for lazy loading
    if bridge.bpy and bridge.bpy.context.scene.world:
        world = bridge.bpy.context.scene.world
        if not world.use_nodes:
            world.use_nodes = True

        # Find the Environment Texture node
        env_node = world.node_tree.nodes.get("Environment Texture")
        if env_node and env_node.image:
            current_path = env_node.image.filepath
            # Compare paths (standardizing to string)
            if current_path == str(hdri_path):
                # HDRI is already loaded, skip redundant setup
                return

    bridge.bproc.world.set_world_background_hdr_img(str(hdri_path))


def setup_lighting(lights: list[Any]) -> list:
    """Set up explicit lighting from recipes.

    Args:
        lights: List of LightRecipe objects (or dicts)

    Returns:
        List of created light objects
    """
    created_lights = []

    for light_data in lights:
        # Support both Pydantic model and dict
        if hasattr(light_data, "model_dump"):
            l_dict = light_data.model_dump()
        else:
            l_dict = light_data

        light = bridge.bproc.types.Light()
        light.set_type(l_dict.get("type", "POINT"))
        light.set_location(l_dict["location"])
        light.set_energy(l_dict["intensity"])
        light.set_color(l_dict.get("color", [1.0, 1.0, 1.0]))

        if l_dict.get("radius", 0) > 0:
            light.set_radius(l_dict["radius"])

        created_lights.append(light)

    return created_lights


def setup_floor_material(
    floor_obj: Any,
    texture_path: str | None = None,
    scale: float = 1.0,
    rotation: float = 0.0,
) -> None:
    """Apply a deterministic, scaled texture to the floor using shader nodes.

    Args:
        floor_obj: The floor mesh object (bridge.bproc.types.MeshObject)
        texture_path: Path to the texture image (optional)
        scale: Tiling scale for the texture
        rotation: Rotation for the texture in radians
    """
    if not texture_path or not Path(texture_path).exists():
        # Fallback: grey if no texture provided
        if floor_obj.blender_obj.data.materials:
            mat = floor_obj.blender_obj.data.materials[0]
        else:
            mat = bridge.bpy.data.materials.new(name="DefaultFloorMat")
            floor_obj.blender_obj.data.materials.append(mat)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
            bsdf.inputs["Roughness"].default_value = 0.9
        return

    try:
        image = bridge.bpy.data.images.load(str(texture_path))
    except Exception as e:
        logger.error(f"Failed to load texture: {texture_path}, error: {e}")
        return

    mat_name = "PooledFloorMat"
    mat = bridge.bpy.data.materials.get(mat_name)
    if not mat:
        mat = bridge.bpy.data.materials.new(name=mat_name)

    if not floor_obj.blender_obj.data.materials or floor_obj.blender_obj.data.materials[0] != mat:
        floor_obj.blender_obj.data.materials.clear()
        floor_obj.blender_obj.data.materials.append(mat)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex_image = nodes.new("ShaderNodeTexImage")
    mapping = nodes.new("ShaderNodeMapping")
    tex_coord = nodes.new("ShaderNodeTexCoord")

    tex_image.image = image
    tex_image.interpolation = "Linear"
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    mapping.inputs["Rotation"].default_value = (0, 0, rotation)
    bsdf.inputs["Roughness"].default_value = 0.9  # Constant for predictability

    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex_image.inputs["Vector"])
    links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])


def create_board(
    cols: int,
    rows: int,
    square_size: float,
    layout_mode: str = "board",
    location: list[float] | None = None,
) -> Any:
    """Create a white background board for layouts.

    Args:
        cols: Number of columns in the grid
        rows: Number of rows in the grid
        square_size: Size of each square (cell)
        layout_mode: Layout mode string for naming
        location: Explicit location [x, y, z]

    Returns:
        The board mesh object
    """
    board_width = cols * square_size
    board_height = rows * square_size

    # Create a simple plane for the board
    board = bridge.bproc.object.create_primitive("PLANE")
    board.blender_obj.name = f"Board_Background_{layout_mode}"
    
    # Use provided location or fallback to default clearance
    if location:
        board.set_location(location)
    else:
        # More clearance below layout (-0.005) to avoid z-fighting with tags/squares at 0 or near 0
        board.set_location([0, 0, -0.005])
    
    board.set_scale([board_width / 2, board_height / 2, 1])
    board.persist_transformation_into_mesh()

    # Pure White Emission Material (fail-safe for high contrast)
    mat = _create_white_emission_material("BoardWhite")

    board.blender_obj.data.materials.clear()
    board.blender_obj.data.materials.append(mat)
    board.enable_rigidbody(active=False)

    return board


def _create_white_emission_material(name: str) -> Any:
    """Create a pure white emission material."""
    mat = bridge.bpy.data.materials.new(name=name)
    mat.diffuse_color = (1, 1, 1, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1, 1, 1, 1)
    emission.inputs["Strength"].default_value = 1.0
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat
