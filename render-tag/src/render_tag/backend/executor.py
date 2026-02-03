import os
import sys

# Move site-packages to the end to prioritize Blender's internal libraries (like NumPy)
# while still allowing blenderproc to be imported if it's uniquely in the venv.
sys.path = [p for p in sys.path if "site-packages" not in p] + [
    p for p in sys.path if "site-packages" in p
]

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import blenderproc as bproc
import numpy as np
from PIL import Image

# Add the src directory to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None

from render_tag.backend.assets import create_tag_plane, get_tag_texture_path
from render_tag.backend.projection import (
    check_tag_facing_camera,
    check_tag_visibility,
    compute_geometric_metadata,
    project_corners_to_image,
)
from render_tag.backend.scene import (
    create_board,
    randomize_floor_material,
    setup_background,
    setup_lighting,
)
from render_tag.data_io.types import DetectionRecord
from render_tag.data_io.writers import COCOWriter, CSVWriter, RichTruthWriter

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def apply_sensor_noise(image: np.ndarray, iso_level: float) -> np.ndarray:
    """Apply Poisson and Gaussian noise to simulate sensor noise.

    Args:
        image: Input RGB image array (0-255).
        iso_level: Noise intensity level (0.0 to 1.0).

    Returns:
        Noisy RGB image array (0-255).
    """
    if iso_level <= 0:
        return image

    img_float = image.astype(np.float32) / 255.0
    # Higher scale = less Poisson noise
    scale = 1000.0 * (1.0 - iso_level * 0.9)
    noisy = np.random.poisson(img_float * scale) / scale

    # Add Gaussian noise for electronic noise
    sigma = 0.01 + (iso_level * 0.1)
    noise = np.random.normal(0, sigma, img_float.shape)

    noisy = np.clip(noisy + noise, 0, 1)
    return (noisy * 255).astype(np.uint8)


def get_valid_detections(
    tag_objects: list[Any],
    min_visible_corners: int = 3,
    require_facing: bool = True,
) -> list[tuple[Any, np.ndarray]]:
    """Determine which tags are adequately visible in the current camera view.

    Args:
        tag_objects: List of Blender objects Representing tags.
        min_visible_corners: Minimum corners that must be in frustum.
        require_facing: If True, tags must be facing the camera.

    Returns:
        List of (tag_object, corners_2d) tuples.
    """
    valid_detections = []
    for tag_obj in tag_objects:
        if not check_tag_visibility(tag_obj, min_visible_corners):
            continue
        if require_facing and not check_tag_facing_camera(tag_obj):
            continue
        corners_2d = project_corners_to_image(tag_obj)
        if corners_2d is None:
            continue
        valid_detections.append((tag_obj, corners_2d))
    return valid_detections


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="BlenderProc render-tag executor")
    parser.add_argument("--recipe", type=Path, required=True, help="Path to scene_recipes.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument(
        "--renderer-mode", choices=["cycles", "workbench", "eevee"], default="cycles"
    )
    parser.add_argument("--shard-id", type=str, default="main", help="Unique ID for output files")
    return parser.parse_args()


def execute_recipe(
    recipe: dict[str, Any],
    output_dir: Path,
    renderer_mode: str,
    csv_writer: CSVWriter,
    coco_writer: COCOWriter,
    rich_writer: RichTruthWriter,
) -> None:
    """Execute a single scene recipe: setup scene, render, and export data."""
    scene_idx = recipe["scene_id"]
    logger.info(f"--- Executing Scene {scene_idx} ---")

    bproc.clean_up()

    # 1. Setup Renderer
    if renderer_mode == "workbench":
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        bpy.data.scenes["Scene"].display.shading.light = "FLAT"
        bpy.data.scenes["Scene"].display.shading.color_type = "TEXTURE"
    elif renderer_mode == "eevee":
        try:
            bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            bpy.context.scene.render.engine = "BLENDER_EEVEE"

    # 2. Setup World (Background and Lighting)
    world_config = recipe.get("world", {})
    hdri_path = world_config.get("background_hdri")
    if hdri_path and Path(hdri_path).is_file():
        setup_background(Path(hdri_path))
    else:
        bpy.context.scene.world.use_nodes = True
        bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            bg_node.inputs[1].default_value = 1.0

    lighting = world_config.get("lighting", {})
    intensity = lighting.get("intensity", 100)
    radius = lighting.get("radius", 0.0)
    setup_lighting(
        intensity_min=intensity,
        intensity_max=intensity,
        radius_min=radius,
        radius_max=radius,
    )

    # 2b. Setup Background Texture (Floor)
    texture_path = world_config.get("texture_path")
    texture_scale = world_config.get("texture_scale", 1.0)
    texture_rotation = world_config.get("texture_rotation", 0.0)

    # Find floor or board objects to apply texture to
    # We apply to the first plane we find that isn't a tag
    all_meshes = bproc.object.get_all_mesh_objects()
    for obj in all_meshes:
        name = obj.get_name()
        if ("Plane" in name or "Board" in name) and "Tag" not in name:
            randomize_floor_material(
                obj,
                texture_path=texture_path,
                scale=texture_scale,
                rotation=texture_rotation,
            )
            break

    # 3. Create Objects
    tag_objects = []
    for obj_recipe in recipe["objects"]:
        if obj_recipe["type"] == "TAG":
            props = obj_recipe["properties"]
            family = props["tag_family"]
            tag_id = props["tag_id"]
            tag_size = props["tag_size"]
            texture_base_path = props.get("texture_base_path")

            texture_path = get_tag_texture_path(family, texture_base_path, tag_id=tag_id)
            tag_obj = create_tag_plane(tag_size, texture_path, family, tag_id=tag_id)

            # Set properties for visibility/segmentation checks
            tag_obj.blender_obj.pass_index = tag_id + 1
            tag_obj.blender_obj["tag_id"] = tag_id
            tag_obj.blender_obj["tag_family"] = family
            tag_obj.blender_obj["category_id"] = tag_id + 1

            tag_obj.set_location(obj_recipe["location"])
            tag_obj.set_rotation_euler(obj_recipe["rotation_euler"])

            if "marker_size" in props:
                current_size = max(tag_obj.blender_obj.dimensions[:2])
                if current_size > 0:
                    scale = props["marker_size"] / current_size
                    tag_obj.set_scale([scale, scale, 1])
                    tag_obj.persist_transformation_into_mesh()

            tag_objects.append(tag_obj)

        elif obj_recipe["type"] == "BOARD":
            props = obj_recipe["properties"]
            create_board(props["cols"], props["rows"], props["square_size"], props["mode"])

    # Update categories in COCO writer
    for tag_obj in tag_objects:
        coco_writer.add_category(tag_obj.blender_obj["tag_family"])

    # 4. Render Loop
    rendered_outputs = []
    cam_recipes = recipe["cameras"]

    for _cam_idx, cam_recipe in enumerate(cam_recipes):
        bproc.utility.reset_keyframes()

        # Add camera pose
        pose_matrix = np.array(cam_recipe["transform_matrix"])
        bproc.camera.add_camera_pose(pose_matrix, frame=0)

        # Handle Sensor Simulation
        velocity = cam_recipe.get("velocity")
        shutter_time_ms = cam_recipe.get("shutter_time_ms", 0.0)
        iso_noise = cam_recipe.get("iso_noise", 0.0)

        # Motion Blur
        if velocity and shutter_time_ms > 0:
            vx, vy, vz = velocity
            dt = shutter_time_ms / 1000.0
            start_matrix = mathutils.Matrix(pose_matrix)
            end_loc = start_matrix.to_translation() + mathutils.Vector((vx * dt, vy * dt, vz * dt))
            end_matrix = start_matrix.copy()
            end_matrix.translation = end_loc

            bproc.camera.add_camera_pose(end_matrix, frame=1)
            bpy.context.scene.render.use_motion_blur = True
            bpy.context.scene.render.motion_blur_shutter = 1.0
        else:
            bpy.context.scene.render.use_motion_blur = False

        # Depth of Field
        fstop = cam_recipe.get("fstop")
        focus_dist = cam_recipe.get("focus_distance")
        cam_data = bpy.context.scene.camera.data
        if fstop:
            cam_data.dof.use_dof = True
            cam_data.dof.aperture_fstop = fstop
            if focus_dist:
                cam_data.dof.focus_distance = focus_dist
        else:
            cam_data.dof.use_dof = False

        # Enable Segmentation and Render
        bproc.renderer.enable_segmentation_output(default_values={"category_id": 0})
        data = bproc.renderer.render()

        if "colors" in data:
            img = data["colors"][0]
            if iso_noise > 0:
                img = apply_sensor_noise(img, iso_noise)
            rendered_outputs.append(img)

    # Dictionary to store all rendered results
    rendered_data = {
        "colors": rendered_outputs,
        "segmaps": data.get("segmentation", []),
    }

    # 5. Export Data
    camera_config = cam_recipes[0]["intrinsics"]
    resolution = camera_config.get("resolution", [640, 480])

    for cam_idx in range(len(cam_recipes)):
        image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
        image_path = output_dir / "images" / f"{image_name}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)

        if "colors" in rendered_data and len(rendered_data["colors"]) > cam_idx:
            img_array = rendered_data["colors"][cam_idx]
            Image.fromarray(img_array.astype(np.uint8)).save(str(image_path))

        coco_image_id = coco_writer.add_image(
            file_name=f"images/{image_path.name}",
            width=resolution[0],
            height=resolution[1],
        )

        # Update Blender state for metadata projection
        frame_pose = bproc.camera.get_camera_pose(cam_idx)
        bpy.context.scene.camera.matrix_world = mathutils.Matrix(frame_pose)
        bpy.context.view_layer.update()

        valid_detections = get_valid_detections(tag_objects)
        segmap = (
            rendered_data["segmaps"][cam_idx]
            if "segmaps" in rendered_data and len(rendered_data["segmaps"]) > cam_idx
            else None
        )

        for tag_obj, corners_2d in valid_detections:
            blender_obj = tag_obj.blender_obj
            tag_id = blender_obj.get("tag_id", 0)
            tag_fam = blender_obj.get("tag_family", "unknown")

            # Calculate Rich Metadata
            geom = compute_geometric_metadata(tag_obj)

            # Calculate Occlusion Metadata via Segmentation Map
            occlusion_ratio = 0.0
            if segmap is not None:
                obj_idx = blender_obj.pass_index
                theoretical_pixels = geom["pixel_area"]
                visible_pixels = np.sum(segmap == obj_idx)

                if theoretical_pixels > 0:
                    vis_ratio = visible_pixels / theoretical_pixels
                    occlusion_ratio = float(np.clip(1.0 - vis_ratio, 0.0, 1.0))

            detection = DetectionRecord(
                image_id=image_name,
                tag_id=tag_id,
                tag_family=tag_fam,
                corners=corners_2d,
                distance=geom["distance"],
                angle_of_incidence=geom["angle_of_incidence"],
                pixel_area=geom["pixel_area"],
                occlusion_ratio=occlusion_ratio,
            )

            # Write to all outputs
            csv_writer.write_detection(detection, resolution[0], resolution[1])
            coco_writer.add_annotation(
                image_id=coco_image_id,
                category_id=coco_writer._category_map.get(tag_fam, 1),
                corners=corners_2d,
                detection=detection,
                width=resolution[0],
                height=resolution[1],
            )
            rich_writer.add_detection(detection)

    logger.info(f"✓ Rendered {len(cam_recipes)} cameras for scene {scene_idx}")


def main() -> None:
    """Main entry point for BlenderProc execution."""
    args = parse_args()
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.recipe) as f:
        recipes = json.load(f)

    bproc.init()

    # Initialize writers
    # Initialize writers
    csv_filename = f"tags_shard_{args.shard_id}.csv"
    csv_writer = CSVWriter(output_dir / csv_filename)
    coco_writer = COCOWriter(output_dir)
    rich_writer = RichTruthWriter(output_dir / "rich_truth.json")

    for recipe in recipes:
        execute_recipe(recipe, output_dir, args.renderer_mode, csv_writer, coco_writer, rich_writer)

    # Save all results
    coco_writer.save()
    rich_writer.save()


if __name__ == "__main__":
    main()
