"""
Scene composition logic for render-tag.

This module orchestrates the creation of tags, application of layouts, 
and setup of board backgrounds.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import blenderproc as bproc

# BlenderProc imports (only available inside Blender)
try:
    import blenderproc as bproc
    import bpy
except ImportError:
    bproc = None  # type: ignore
    bpy = None  # type: ignore

from render_tag.scripts.assets import create_tag_plane, get_tag_texture_path
from render_tag.common.constants import TAG_BIT_COUNTS, TAG_GRID_SIZES
from render_tag.scripts.layouts import apply_layout
from render_tag.scripts.scene import create_board, create_floor, create_flying_layout


def compose_scene(
    scene_idx: int,
    tag_config: dict,
    scenario_config: dict,
    scene_config: dict,
    physics_config: dict,
    tag_families: list[str],
) -> tuple[list[Any], list[Any], str]:
    """Compose the scene by creating tags and applying layout.

    Args:
        scene_idx: Index of the current scene (0-based)
        tag_config: Tag configuration dictionary
        scenario_config: Scenario configuration dictionary
        scene_config: Scene configuration dictionary
        physics_config: Physics configuration dictionary
        tag_families: List of tag families to use

    Returns:
        Tuple of (tag_objects, layout_objects, layout_mode)
    """
    # Get scenario flags
    is_flying = scenario_config.get("flying", False)

    # Select layout for this scene
    layout_list = scene_config.get("layouts", scenario_config.get("layouts"))
    if layout_list:
        layout_mode = layout_list[scene_idx % len(layout_list)]
    else:
        layout_mode = scene_config.get("layout", scenario_config.get("layout", "plain"))

    # Create floor if NOT flying and NOT a board layout
    # Note: create_floor returns a single object, but we don't need to track it 
    # in layout_objects if it's passive/static floor unless we want to move it.
    # However, blender_main previously created it but didn't return it to a list 
    # unless it was part of physics setup?
    # In blender_main, create_floor() was called but return value ignored. 
    # It creates a static object internally.
    if not is_flying and layout_mode not in ("cb", "aprilgrid", "plain"):
        create_floor()

    # Determine number of tags for this scene
    grid_size = tag_config.get("grid_size", scenario_config.get("grid_size", [6, 6]))
    cols, rows = grid_size[0], grid_size[1]
    num_tags = 0

    if layout_mode == "cb":
        # ChArUco board: tags go in alternating (white) squares
        total_squares = cols * rows
        num_tags = (total_squares + 1) // 2  # Ceiling division
    elif layout_mode == "aprilgrid":
        # AprilGrid/Kalibr: tags in every cell
        num_tags = cols * rows
    else:
        tags_range = tag_config.get("tags_per_scene", scenario_config.get("tags_per_scene", [1, 5]))
        num_tags = random.randint(tags_range[0], tags_range[1])
        # For plain board, calculate grid dimensions based on tag count
        if layout_mode == "plain" and (cols * rows < num_tags):
             # For plain layout (non-fixed grid), recalc cols/rows to fit tags
             cols = math.ceil(math.sqrt(num_tags))
             rows = math.ceil(num_tags / cols)

    # Create tag objects
    tag_objects = []
    tag_size = tag_config.get("size_meters", 0.1)
    texture_base_path = tag_config.get("texture_path")

    for i in range(num_tags):
        family = random.choice(tag_families)
        texture_path = get_tag_texture_path(family, texture_base_path, tag_id=i)

        # Create tag with random ID (handled by texture loader usually, but here just reuse)
        tag_obj = create_tag_plane(tag_size, texture_path, family, tag_id=i)

        # Set custom properties for ground truth
        tag_obj.blender_obj["tag_id"] = i  # Placeholder ID, ideally from texture
        tag_obj.blender_obj["tag_family"] = family

        tag_objects.append(tag_obj)

    # Apply layout
    layout_objects = []

    if is_flying:
        # Flying mode: ignore layout and scatter in volume
        create_flying_layout(
            tag_objects, volume_size=tag_config.get("scatter_radius", 0.5) * 2
        )
    else:
        # Standard mode: apply layout and settle with physics
        
        # Calculate spacing logic
        primary_family = tag_families[0]
        tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
        
        # Default to 2 bits spacing if nothing specified
        tag_spacing_bits = scenario_config.get("tag_spacing_bits", 
                                             tag_config.get("tag_spacing_bits", 2))
        
        # Calculate from bits
        tag_spacing = (tag_spacing_bits / tag_bit_grid_size) * tag_size
        
        square_size = tag_size + tag_spacing
        marker_margin = tag_spacing / 2.0
        corner_size = tag_spacing

        # Apply layout
        new_objects = apply_layout(
            tag_objects=tag_objects,
            layout_mode=layout_mode,
            spacing=tag_spacing,
            tag_size=tag_size,
            square_size=square_size,
            marker_margin=marker_margin,
            corner_size=corner_size,
            center=(0, 0, 0),
            cols=cols,
            rows=rows,
        )
        layout_objects.extend(new_objects)

        # Create board if needed
        if layout_mode in ("cb", "aprilgrid", "plain"):
            board = create_board(cols, rows, square_size, layout_mode)
            layout_objects.append(board)

        # Setup physics
        _setup_physics_for_objects(tag_objects, layout_objects, physics_config)

    # CRITICAL: Update scene after all objects are placed
    if bpy:
        bpy.context.view_layer.update()

    return tag_objects, layout_objects, layout_mode


def _setup_physics_for_objects(
    tag_objects: list[Any],
    layout_objects: list[Any],
    physics_config: dict,
) -> None:
    """Setup physics properties and run simulation if needed."""
    drop_height = physics_config.get("drop_height", 0.1)
    simulate_physics = drop_height > 0

    # Ensure tags are on top
    for obj in tag_objects:
        loc = obj.get_location()
        if simulate_physics:
            obj.set_location([loc[0], loc[1], drop_height + 0.002])
            obj.enable_rigidbody(active=True)
        else:
            obj.set_location([loc[0], loc[1], 0.002])
            obj.enable_rigidbody(active=False)

    # Ensure layout objects (boards, squares) are correctly placed
    for obj in layout_objects:
        loc = obj.get_location()
        if "Board_Background" in obj.blender_obj.name:
            # Board stays at Z=0 (actually created at -0.005 in create_board)
            # Just ensure it's passive
            obj.enable_rigidbody(active=False)
        else:
            # Other layout elements (black squares, corners)
            if simulate_physics:
                obj.set_location([loc[0], loc[1], drop_height + 0.001])
                obj.enable_rigidbody(active=True)
            else:
                obj.set_location([loc[0], loc[1], 0.001])
                obj.enable_rigidbody(active=False)

    if simulate_physics:
        bproc.object.simulate_physics_and_fix_final_poses(
            min_simulation_time=1,
            check_object_interval=1,
        )
