"""
Scene construction utilities for render-tag.

This module handles background setup, lighting, floor creation, and physics.
"""

from __future__ import annotations

import random
from pathlib import Path
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


def setup_background(hdri_path: Path) -> None:
    """Set the world background using an HDRI image.

    Args:
        hdri_path: Path to the HDRI image file (.exr or .hdr)
    """
    if not hdri_path.exists():
        print(f"Warning: HDRI path does not exist: {hdri_path}")
        return

    bproc.world.set_world_background_hdr_img(str(hdri_path))


def setup_lighting(
    intensity_min: float = 50,
    intensity_max: float = 500,
    radius_min: float = 0.0,
    radius_max: float = 0.0,
    num_lights: int = 3,
) -> list:
    """Set up randomized lighting for the scene.

    Args:
        intensity_min: Minimum light intensity
        intensity_max: Maximum light intensity
        num_lights: Number of point lights to add

    Returns:
        List of created light objects
    """
    lights = []

    for _ in range(num_lights):
        # Random position in a hemisphere above the scene
        theta = random.uniform(0, 2 * 3.14159)
        phi = random.uniform(0.2, 0.8) * 3.14159 / 2  # Bias towards top
        radius = random.uniform(2, 5)

        x = radius * np.sin(phi) * np.cos(theta)
        y = radius * np.sin(phi) * np.sin(theta)
        z = radius * np.cos(phi)

        # Random intensity
        intensity = random.uniform(intensity_min, intensity_max)

        # Random color temperature (warm to cool white)
        color_temp = random.uniform(0.9, 1.0)
        color = (color_temp, color_temp, 1.0)

        # Create point light
        light = bproc.types.Light()
        light.set_type("POINT")
        light.set_location([x, y, z])
        light.set_energy(intensity)
        light.set_color(color)

        if radius_max > 0 or radius_min > 0:
            samp_radius = random.uniform(radius_min, radius_max)
            light.set_radius(samp_radius)

        lights.append(light)

    return lights


def create_floor(
    size: float = 10.0,
    location: tuple = (0, 0, 0),
) -> Any:
    """Create a passive floor plane for physics simulation.

    Args:
        size: Size of the floor in meters
        location: Center location of the floor

    Returns:
        The floor mesh object
    """
    # Create floor plane
    floor = bproc.object.create_primitive("PLANE")
    floor.set_location(list(location))
    floor.set_scale([size, size, 1])
    floor.persist_transformation_into_mesh()

    # Make it invisible to camera (optional, for cleaner renders)
    # floor.blender_obj.hide_render = True

    # Apply a neutral material
    material = bpy.data.materials.new(name="FloorMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
        bsdf.inputs["Roughness"].default_value = 0.9

    floor.blender_obj.data.materials.clear()
    floor.blender_obj.data.materials.append(material)

    # Enable physics as passive (static) object
    floor.enable_rigidbody(
        active=False,  # Passive (doesn't move)
        collision_shape="BOX",
        friction=0.5,
    )

    return floor


def scatter_tags(
    tag_objects: list,
    drop_height: float = 1.5,
    scatter_radius: float = 0.5,
) -> None:
    """Scatter tags randomly above the floor for physics simulation.

    Args:
        tag_objects: List of tag mesh objects to scatter
        drop_height: Height above ground to drop from
        scatter_radius: Radius of scatter area
    """
    for tag in tag_objects:
        # Random position within scatter radius
        x = random.uniform(-scatter_radius, scatter_radius)
        y = random.uniform(-scatter_radius, scatter_radius)
        z = drop_height + random.uniform(0, 0.5)

        # Random rotation
        rx = random.uniform(0, 2 * 3.14159)
        ry = random.uniform(0, 2 * 3.14159)
        rz = random.uniform(0, 2 * 3.14159)

        tag.set_location([x, y, z])
        tag.set_rotation_euler([rx, ry, rz])

        # Enable physics as active (dynamic) object
        tag.enable_rigidbody(
            active=True,
            collision_shape="BOX",
            mass=0.01,  # Light like a printed tag
            friction=0.5,
        )


def create_flying_layout(
    tag_objects: list,
    volume_size: float = 2.0,
) -> None:
    """Randomly position and rotate tags in a 3D volume.

    Args:
        tag_objects: List of tag mesh objects
        volume_size: Size of the box volume (meters)
    """
    for tag in tag_objects:
        # Random position in a 3D box centered at (0, 0, volume_size/2)
        x = random.uniform(-volume_size / 2, volume_size / 2)
        y = random.uniform(-volume_size / 2, volume_size / 2)
        z = random.uniform(0.5, volume_size + 0.5)  # Stay above "ground" even if no ground

        # Completely random rotation
        rx = random.uniform(0, 2 * 3.14159)
        ry = random.uniform(0, 2 * 3.14159)
        rz = random.uniform(0, 2 * 3.14159)

        tag.set_location([x, y, z])
        tag.set_rotation_euler([rx, ry, rz])

        # Tags stay fixed in space (no gravity/physics needed for flying)
        # or we could make them active with 0 gravity, but fixed is simpler.
        tag.enable_rigidbody(active=False)  # Static in air


def randomize_floor_material(floor: Any, texture_dir: Path | None = None) -> None:
    """Randomize the floor material for domain randomization.

    Args:
        floor: The floor mesh object
        texture_dir: Optional directory containing PBR texture sets
    """
    if texture_dir and texture_dir.exists():
        # Load random texture from directory
        textures = list(texture_dir.glob("*.jpg")) + list(texture_dir.glob("*.png"))
        if textures:
            texture_path = random.choice(textures)
            image = bpy.data.images.load(str(texture_path))

            material = (
                floor.blender_obj.data.materials[0]
                if floor.blender_obj.data.materials
                else bpy.data.materials.new(name="RandomFloor")
            )
            material.use_nodes = True

            nodes = material.node_tree.nodes
            links = material.node_tree.links

            # Add texture node
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = image

            bsdf = nodes.get("Principled BSDF")
            if bsdf:
                links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

            return

    # Fallback: randomize color
    material = floor.blender_obj.data.materials[0] if floor.blender_obj.data.materials else None
    if material:
        nodes = material.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            r = random.uniform(0.1, 0.8)
            g = random.uniform(0.1, 0.8)
            b = random.uniform(0.1, 0.8)
            bsdf.inputs["Base Color"].default_value = (r, g, b, 1)


def create_board(
    cols: int,
    rows: int,
    square_size: float,
    layout_mode: str = "board",
) -> Any:
    """Create a white background board for layouts.

    Args:
        cols: Number of columns in the grid
        rows: Number of rows in the grid
        square_size: Size of each square (cell)
        layout_mode: Layout mode string for naming

    Returns:
        The board mesh object
    """
    board_width = cols * square_size
    board_height = rows * square_size

    # Create a simple plane for the board
    board = bproc.object.create_primitive("PLANE")
    board.blender_obj.name = f"Board_Background_{layout_mode}"
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
    mat = bpy.data.materials.new(name=name)
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
