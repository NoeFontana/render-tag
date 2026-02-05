"""
Core rendering loop logic, extracted for reuse in both CLI and persistent backend.
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone

import numpy as np
from PIL import Image

try:
    import blenderproc as bproc
    import bpy
except ImportError:
    bproc = None
    bpy = None

from render_tag.backend.assets import create_tag_plane, get_tag_texture_path, global_pool
from render_tag.backend.camera import setup_sensor_dynamics
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
from render_tag.backend.sensors import apply_parametric_noise
from render_tag.common.git import get_git_hash
from render_tag.data_io.types import DetectionRecord
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

logger = logging.getLogger(__name__)

def apply_sensor_noise(image: np.ndarray, iso_level: float) -> np.ndarray:
    if iso_level <= 0: return image
    img_float = image.astype(np.float32) / 255.0
    scale = 1000.0 * (1.0 - iso_level * 0.9)
    noisy = np.random.poisson(img_float * scale) / scale
    sigma = 0.01 + (iso_level * 0.1)
    noise = np.random.normal(0, sigma, img_float.shape)
    return (np.clip(noisy + noise, 0, 1) * 255).astype(np.uint8)

def get_valid_detections(tag_objects, min_visible_corners=3, require_facing=True):
    valid = []
    for tag_obj in tag_objects:
        if not check_tag_visibility(tag_obj, min_visible_corners): continue
        if require_facing and not check_tag_facing_camera(tag_obj): continue
        corners_2d = project_corners_to_image(tag_obj)
        if corners_2d is not None:
            valid.append((tag_obj, corners_2d))
    return valid

def execute_recipe(
    recipe: dict[str, Any],
    output_dir: Path,
    renderer_mode: str,
    csv_writer: CSVWriter,
    coco_writer: COCOWriter,
    rich_writer: RichTruthWriter,
    sidecar_writer: SidecarWriter,
    skip_visibility: bool = False,
) -> None:
    """Execute a single scene recipe."""
    scene_idx = recipe["scene_id"]
    logger.info(f"--- Executing Scene {scene_idx} ---")

    if np: np.random.seed(scene_idx)
    random.seed(scene_idx)
    if bpy:
        bpy.context.scene.cycles.seed = scene_idx
        bpy.context.scene.cycles.use_animated_seed = False

    git_hash = get_git_hash()
    timestamp = datetime.now(timezone.utc).isoformat()
    provenance = {
        "git_hash": git_hash,
        "timestamp": timestamp,
        "recipe_snapshot": recipe,
        "seeds": None,
    }

    # IMPORTANT: We use the pool to avoid deletion/creation overhead
    global_pool.release_all()

    # 1. Setup Renderer
    if bpy:
        if renderer_mode == "workbench":
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        elif renderer_mode == "eevee":
            try: bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
            except: bpy.context.scene.render.engine = "BLENDER_EEVEE"
        else:
            bpy.context.scene.render.engine = "CYCLES"

    # 2. Setup World
    world_config = recipe.get("world", {})
    hdri_path = world_config.get("background_hdri")
    if hdri_path and Path(hdri_path).is_file():
        setup_background(Path(hdri_path))

    lighting = world_config.get("lighting", {})
    setup_lighting(
        intensity_min=lighting.get("intensity", 100),
        intensity_max=lighting.get("intensity", 100),
        radius_min=lighting.get("radius", 0.0),
        radius_max=lighting.get("radius", 0.0),
    )

    # 3. Create Objects
    tag_objects = []
    for obj_recipe in recipe["objects"]:
        if obj_recipe["type"] == "TAG":
            props = obj_recipe["properties"]
            texture_path = get_tag_texture_path(props["tag_family"], tag_id=props["tag_id"])
            tag_obj = create_tag_plane(props["tag_size"], texture_path, props["tag_family"], tag_id=props["tag_id"])
            tag_obj.blender_obj.pass_index = props["tag_id"] + 1
            tag_obj.set_location(obj_recipe["location"])
            tag_obj.set_rotation_euler(obj_recipe["rotation_euler"])
            tag_objects.append(tag_obj)
            coco_writer.add_category(props["tag_family"])
        elif obj_recipe["type"] == "BOARD":
            props = obj_recipe["properties"]
            create_board(props["cols"], props["rows"], props["square_size"], props["mode"])

    # 4. Render
    rendered_outputs = []
    cam_recipes = recipe["cameras"]
    for cam_recipe in cam_recipes:
        if bproc:
            bproc.utility.reset_keyframes()
            pose_matrix = np.array(cam_recipe["transform_matrix"])
            bproc.camera.add_camera_pose(pose_matrix, frame=0)
            setup_sensor_dynamics(pose_matrix, cam_recipe.get("sensor_dynamics"))
            
            if bpy:
                cam_data = bpy.context.scene.camera.data
                if cam_recipe.get("fstop"):
                    cam_data.dof.use_dof = True
                    cam_data.dof.aperture_fstop = cam_recipe["fstop"]
                    if cam_recipe.get("focus_distance"):
                        cam_data.dof.focus_distance = cam_recipe["focus_distance"]
                else:
                    cam_data.dof.use_dof = False

            if bpy and bpy.context.scene.render.engine != "BLENDER_WORKBENCH":
                bproc.renderer.enable_segmentation_output(default_values={"category_id": 0})
            
            data = bproc.renderer.render()
            img = data["colors"][0]
            
            if cam_recipe.get("sensor_noise"):
                img = apply_parametric_noise(img, cam_recipe["sensor_noise"])
            elif cam_recipe.get("iso_noise", 0) > 0:
                img = apply_sensor_noise(img, cam_recipe["iso_noise"])
            
            rendered_outputs.append({
                "img": img,
                "segmap": data.get("segmentation", [None])[0]
            })

    # 5. Export
    camera_config = cam_recipes[0]["intrinsics"]
    res = camera_config.get("resolution", [640, 480])

    for cam_idx, render_out in enumerate(rendered_outputs):
        image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
        image_path = output_dir / "images" / f"{image_name}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        
        Image.fromarray(render_out["img"].astype(np.uint8)).save(str(image_path))
        sidecar_writer.write_sidecar(image_name, provenance)
        coco_img_id = coco_writer.add_image(f"images/{image_path.name}", res[0], res[1])

        if bpy:
            bpy.context.scene.frame_set(0, subframe=0.5)
            bpy.context.view_layer.update()

        if skip_visibility:
            valid_detections = [(obj, [[0,0],[res[0],0],[res[0],res[1]],[0,res[1]]]) for obj in tag_objects]
        else:
            valid_detections = get_valid_detections(tag_objects)
        
        segmap = render_out["segmap"]

        for tag_obj, corners_2d in valid_detections:
            blender_obj = tag_obj.blender_obj
            geom = compute_geometric_metadata(tag_obj)
            
            occlusion = 0.0
            if segmap is not None:
                vis_pixels = np.sum(segmap == blender_obj.pass_index)
                if geom["pixel_area"] > 0:
                    occlusion = float(np.clip(1.0 - (vis_pixels / geom["pixel_area"]), 0.0, 1.0))

            det = DetectionRecord(
                image_id=image_name,
                tag_id=blender_obj.get("tag_id", 0),
                tag_family=blender_obj.get("tag_family", "unknown"),
                corners=corners_2d,
                distance=geom["distance"],
                angle_of_incidence=geom["angle_of_incidence"],
                pixel_area=geom["pixel_area"],
                occlusion_ratio=occlusion,
            )
            csv_writer.write_detection(det, res[0], res[1])
            coco_writer.add_annotation(
                image_id=coco_img_id,
                category_id=coco_writer._category_map.get(det.tag_family, 1),
                corners=corners_2d,
                width=res[0],
                height=res[1],
                detection=det
            )
            rich_writer.add_detection(det)

    logger.info(f"✓ Rendered scene {scene_idx}")
