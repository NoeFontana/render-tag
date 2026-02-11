"""
Core rendering loop logic, refactored to use RenderFacade and pure geometry math.
"""

import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from render_tag.backend.bridge import bpy, np
from render_tag.backend.projection import compute_geometric_metadata
from render_tag.backend.renderer import RenderFacade
from render_tag.common.git import get_git_hash
from render_tag.schema import DetectionRecord
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

logger = logging.getLogger(__name__)


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
    """Execute a single scene recipe using the RenderFacade."""
    scene_idx = recipe["scene_id"]
    logger.info(f"--- Executing Scene {scene_idx} ---")

    # 1. Determinism
    if np:
        np.random.seed(scene_idx)
    random.seed(scene_idx)
    if bpy:
        bpy.context.scene.cycles.seed = scene_idx
        bpy.context.scene.cycles.use_animated_seed = False

    # 2. Setup Facade
    renderer = RenderFacade(renderer_mode=renderer_mode)
    renderer.reset_volatile_state()

    # 3. Build Scene
    renderer.setup_world(recipe.get("world", {}))
    tag_objects = renderer.spawn_objects(recipe.get("objects", []))

    # Update COCO categories
    for tag in tag_objects:
        coco_writer.add_category(tag.blender_obj["tag_family"])

    # 4. Render Cameras
    cam_recipes = recipe["cameras"]
    res = cam_recipes[0]["intrinsics"].get("resolution", [640, 480])

    provenance = {
        "git_hash": get_git_hash(),
        "timestamp": datetime.now(UTC).isoformat(),
        "recipe_snapshot": recipe,
    }

    for cam_idx, cam_recipe in enumerate(cam_recipes):
        render_out = renderer.render_camera(cam_recipe)

        image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
        image_path = output_dir / "images" / f"{image_name}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)

        # Save Image
        if len(render_out["img"]) > 0:
            Image.fromarray(render_out["img"].astype(np.uint8)).save(str(image_path))

        sidecar_writer.write_sidecar(image_name, provenance)
        coco_img_id = coco_writer.add_image(f"images/{image_path.name}", res[0], res[1])

        # Subframe alignment for metadata
        if bpy:
            bpy.context.scene.frame_set(0, subframe=0.5)
            bpy.context.view_layer.update()

        # 5. Metadata Projection & Export
        # (We use the project_corners_to_image which now uses pure math)

        if skip_visibility:
            valid_detections = []
            for obj in tag_objects:
                full_rect = [[0, 0], [res[0], 0], [res[0], res[1]], [0, res[1]]]
                valid_detections.append((obj, full_rect))
        else:
            # We keep the legacy filter for now, but it uses bridge internally
            from render_tag.backend.projection import get_valid_detections

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
                detection=det,
            )
            rich_writer.add_detection(det)

    logger.info(f"✓ Rendered scene {scene_idx}")
