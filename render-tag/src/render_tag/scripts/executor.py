import blenderproc as bproc
import argparse
import json
import sys
from pathlib import Path
import numpy as np

# Add the src directory to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    import bpy
    import mathutils
except ImportError:
    bpy = None

from render_tag.scripts.assets import create_tag_plane, get_tag_texture_path
from render_tag.scripts.camera import set_camera_intrinsics
from render_tag.scripts.scene import setup_background, setup_lighting, create_board, create_floor
from render_tag.scripts.projection import is_tag_sufficiently_visible, project_corners_to_image, check_tag_visibility, check_tag_facing_camera
from render_tag.data_io.writers import COCOWriter, CSVWriter
from render_tag.data_io.types import DetectionRecord
from render_tag.common.constants import TAG_BIT_COUNTS


def get_valid_detections(
    tag_objects: list,
    min_visible_corners: int = 3,
    require_facing: bool = True,
) -> list[tuple]:
    """Get detections for visible, properly-facing tags."""
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


def parse_args():
    parser = argparse.ArgumentParser(description="BlenderProc render-tag executor")
    parser.add_argument("--recipe", type=Path, required=True, help="Path to scene_recipes.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--renderer-mode", choices=["cycles", "workbench", "eevee"], default="cycles")
    return parser.parse_args()


def execute_recipe(recipe, output_dir, renderer_mode, csv_writer, coco_writer):
    scene_idx = recipe["scene_id"]
    print(f"--- Executing Scene {scene_idx} ---")
    
    bproc.clean_up()
    
    # 1. Renderer Setup
    if renderer_mode == "workbench":
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        bpy.data.scenes["Scene"].display.shading.light = "FLAT"
        bpy.data.scenes["Scene"].display.shading.color_type = "TEXTURE"
    elif renderer_mode == "eevee":
        try:
            bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            bpy.context.scene.render.engine = "BLENDER_EEVEE"

    # 2. World Setup
    world_config = recipe.get("world", {})
    hdri_path = world_config.get("background_hdri")
    if hdri_path and Path(hdri_path).is_file():
        setup_background(Path(hdri_path))
    else:
        # Default white
        bpy.context.scene.world.use_nodes = True
        bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            bg_node.inputs[1].default_value = 1.0

    lighting = world_config.get("lighting", {})
    intensity = lighting.get("intensity", 100)
    setup_lighting(intensity_min=intensity, intensity_max=intensity)

    # 3. Object Setup
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
            
            # Apply placement from recipe
            tag_obj.set_location(obj_recipe["location"])
            tag_obj.set_rotation_euler(obj_recipe["rotation_euler"])
            
            # Handle scaling if marker_size property exists
            if "marker_size" in props:
                current_size = max(tag_obj.blender_obj.dimensions[:2])
                if current_size > 0:
                    scale = props["marker_size"] / current_size
                    tag_obj.set_scale([scale, scale, 1])
                    tag_obj.persist_transformation_into_mesh()
            
            tag_obj.blender_obj["tag_id"] = tag_id
            tag_obj.blender_obj["tag_family"] = family
            tag_objects.append(tag_obj)
            
        elif obj_recipe["type"] == "BOARD":
            props = obj_recipe["properties"]
            # Map generator's BOARD to scripts.scene.create_board
            create_board(props["cols"], props["rows"], props["square_size"], props["mode"])
        
    # 4. Camera Setup and Rendering
    # CSV and COCO writers are passed from main()
    
    # Add categories to COCO (Simplified)
    for tag_obj in tag_objects:
        coco_writer.add_category(tag_obj.blender_obj["tag_family"])

    for cam_idx, cam_recipe in enumerate(recipe["cameras"]):
        # Set intrinsics (only needs to be done once if they are same, but recipes allow per-camera)
        set_camera_intrinsics(cam_recipe)
        
        # Add pose
        pose_matrix = np.array(cam_recipe["transform_matrix"])
        bproc.camera.add_camera_pose(pose_matrix)
        
        # In this simplistic executor, we render one by one or all at once?
        # blenderproc.renderer.render() renders ALL added poses.
        # But for visibility checks we need to iterate.
    
    rendered_data = bproc.renderer.render()
    
    # Process each rendered frame
    # Resolution for COCO and CSV
    camera_config = recipe["cameras"][0]["intrinsics"] # Assume same for all for now
    resolution = camera_config.get("resolution", [640, 480])

    for cam_idx in range(len(recipe["cameras"])):
        image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
        image_path = output_dir / "images" / f"{image_name}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)

        # Save frame from rendered data
        if "colors" in rendered_data and len(rendered_data["colors"]) > cam_idx:
            from PIL import Image
            img_array = rendered_data["colors"][cam_idx]
            Image.fromarray(img_array.astype(np.uint8)).save(str(image_path))

        # Add image to COCO dataset
        coco_image_id = coco_writer.add_image(
            file_name=f"images/{image_path.name}",
            width=resolution[0],
            height=resolution[1],
        )

        # CRITICAL: Manually update camera matrix to match this frame for visibility writing
        frame_pose = bproc.camera.get_camera_pose(cam_idx)
        bpy.context.scene.camera.matrix_world = mathutils.Matrix(frame_pose)
        bpy.context.view_layer.update()

        # Get valid detections (visible, facing camera)
        # Note: We use the same min_visible_corners and require_facing as blender_main.py defaults
        valid_detections = get_valid_detections(tag_objects)

        # Write detections
        for tag_obj, corners_2d in valid_detections:
            blender_obj = tag_obj.blender_obj
            tag_id = blender_obj.get("tag_id", 0)
            tag_fam = blender_obj.get("tag_family", "unknown")

            # Write to CSV
            detection = DetectionRecord(
                image_id=image_name,
                tag_id=tag_id,
                tag_family=tag_fam,
                corners=corners_2d,
            )
            csv_writer.write_detection(
                detection, width=resolution[0], height=resolution[1]
            )

            # Write to COCO
            coco_writer.add_annotation(
                image_id=coco_image_id,
                category_id=coco_writer._category_map.get(tag_fam, 1),
                corners=corners_2d,
                tag_id=tag_id,
                width=resolution[0],
                height=resolution[1],
            )

    coco_writer.save()
    print(f"✓ Rendered {len(recipe['cameras'])} cameras for scene {scene_idx}")


def main():
    args = parse_args()
    with open(args.recipe) as f:
        recipes = json.load(f)
    
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    
    bproc.init()
    
    # Initialize writers once for the entire run
    csv_writer = CSVWriter(output_dir / "tags.csv")
    coco_writer = COCOWriter(output_dir)

    # Add tag families to COCO categories from all recipes if possible, 
    # but add_category is idempotent so we can do it lazily.

    for recipe in recipes:
        execute_recipe(recipe, output_dir, args.renderer_mode, csv_writer, coco_writer)
    
    # Save COCO once at the end
    coco_writer.save()

if __name__ == "__main__":
    sys.exit(main())
