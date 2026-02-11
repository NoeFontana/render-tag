"""
Facade for the Blender rendering engine.

Provides a simplified interface for scene construction and image generation,
abstracting away the details of BlenderProc and Blender internals.
"""

import logging
from pathlib import Path
from typing import Any

from render_tag.backend.assets import create_tag_plane, get_tag_texture_path, global_pool
from render_tag.backend.bridge import bproc, bpy, np
from render_tag.backend.camera import setup_sensor_dynamics
from render_tag.backend.scene import (
    create_board,
    setup_background,
    setup_lighting,
)
from render_tag.backend.sensors import apply_parametric_noise

logger = logging.getLogger(__name__)


class RenderFacade:
    """
    High-level interface for rendering fiducial tag scenes.
    """

    def __init__(self, renderer_mode: str = "cycles"):
        self.renderer_mode = renderer_mode
        self._configure_engine()

    def _configure_engine(self):
        """Standardizes engine-specific settings."""
        if not bpy:
            return

        if self.renderer_mode == "workbench":
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        elif self.renderer_mode == "eevee":
            try:
                bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
            except Exception:
                bpy.context.scene.render.engine = "BLENDER_EEVEE"
        else:
            bpy.context.scene.render.engine = "CYCLES"

    def reset_volatile_state(self):
        """Clears objects from the scene but keeps heavy environment assets resident."""
        global_pool.release_all()
        if bproc:
            bproc.utility.reset_keyframes()

    def setup_world(self, world_recipe: dict[str, Any]):
        """Sets up HDRI, lighting, and floor."""
        if not bproc:
            return

        hdri_path = world_recipe.get("background_hdri")
        if hdri_path and Path(hdri_path).is_file():
            setup_background(Path(hdri_path))

        lighting = world_recipe.get("lighting", {})
        setup_lighting(
            intensity_min=lighting.get("intensity", 100),
            intensity_max=lighting.get("intensity", 100),
            radius_min=lighting.get("radius", 0.0),
            radius_max=lighting.get("radius", 0.0),
        )

    def spawn_objects(self, object_recipes: list[dict[str, Any]]):
        """Creates tags and boards in the scene."""
        tag_objects = []
        for obj_recipe in object_recipes:
            if obj_recipe["type"] == "TAG":
                props = obj_recipe["properties"]
                texture_path = get_tag_texture_path(props["tag_family"], tag_id=props["tag_id"])
                tag_obj = create_tag_plane(
                    props["tag_size"], texture_path, props["tag_family"], tag_id=props["tag_id"]
                )

                tag_obj.blender_obj.pass_index = props["tag_id"] + 1
                tag_obj.set_location(obj_recipe["location"])
                tag_obj.set_rotation_euler(obj_recipe["rotation_euler"])
                tag_objects.append(tag_obj)

            elif obj_recipe["type"] == "BOARD":
                props = obj_recipe["properties"]
                create_board(props["cols"], props["rows"], props["square_size"], props["mode"])
        return tag_objects

    def render_camera(self, camera_recipe: dict[str, Any]) -> dict[str, Any]:
        """Configures a camera and renders the image."""
        if not bproc:
            return {"colors": [], "segmentation": []}

        pose_matrix = np.array(camera_recipe["transform_matrix"])
        bproc.camera.add_camera_pose(pose_matrix, frame=0)
        setup_sensor_dynamics(pose_matrix, camera_recipe.get("sensor_dynamics"))

        if bpy:
            cam_data = bpy.context.scene.camera.data
            fstop = camera_recipe.get("fstop")
            if fstop:
                cam_data.dof.use_dof = True
                cam_data.dof.aperture_fstop = fstop
                focus_dist = camera_recipe.get("focus_distance")
                if focus_dist:
                    cam_data.dof.focus_distance = focus_dist
            else:
                cam_data.dof.use_dof = False

        if bpy and bpy.context.scene.render.engine != "BLENDER_WORKBENCH":
            bproc.renderer.enable_segmentation_output(default_values={"category_id": 0})

        data = bproc.renderer.render()
        img = data["colors"][0]

        # Apply noise post-processing
        if camera_recipe.get("sensor_noise"):
            img = apply_parametric_noise(img, camera_recipe["sensor_noise"])

        return {"img": img, "segmap": data.get("segmentation", [None])[0]}
