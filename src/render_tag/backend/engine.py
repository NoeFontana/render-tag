"""
Unified rendering engine for render-tag.

Combines the RenderFacade (Blender abstraction) and the execution loop
into a single, high-performance module.
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from PIL import Image

from render_tag.backend.assets import create_tag_plane, global_pool
from render_tag.backend.bridge import bridge
from render_tag.backend.camera import setup_sensor_dynamics
from render_tag.backend.scene import (
    create_board,
    create_board_plane,
    setup_background,
    setup_floor_material,
    setup_lighting,
)
from render_tag.backend.sensors import apply_parametric_noise
from render_tag.core.logging import get_logger
from render_tag.core.schema import DetectionRecord, RendererConfig, SceneRecipe
from render_tag.core.utils import get_git_hash
from render_tag.data_io.writers import (
    COCOWriter,
    CSVWriter,
    RichTruthWriter,
    SidecarWriter,
)

logger = get_logger(__name__)


@dataclass
class RenderContext:
    """Groups all necessary state for executing a single render task."""

    output_dir: Path
    renderer_mode: str
    csv_writer: CSVWriter
    coco_writer: COCOWriter
    rich_writer: RichTruthWriter
    sidecar_writer: SidecarWriter
    global_seed: int
    logger: Any = None
    skip_visibility: bool = False


@runtime_checkable
class RenderEngineStrategy(Protocol):
    """Protocol for rendering engine configuration strategies."""

    def configure(self) -> None:
        """Configure the Blender scene for this specific engine."""
        ...


class CyclesRenderStrategy:
    """Configures the high-fidelity Cycles path tracer."""

    def configure(self) -> None:
        bridge.bpy.context.scene.render.engine = "CYCLES"


class EeveeRenderStrategy:
    """Configures the real-time Eevee engine."""

    def configure(self) -> None:
        try:
            bridge.bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            bridge.bpy.context.scene.render.engine = "BLENDER_EEVEE"


class WorkbenchRenderStrategy:
    """Configures the fast Workbench engine for previews."""

    def configure(self) -> None:
        bridge.bpy.context.scene.render.engine = "BLENDER_WORKBENCH"


class RenderFacade:
    """
    High-level interface for rendering fiducial tag scenes.
    """

    def __init__(
        self,
        renderer_mode: str = "cycles",
        logger: logging.Logger | None = None,
        config: RendererConfig | None = None,
    ):
        # Ensure bridge is stabilized before using it
        if not bridge.bpy or not bridge.bproc:
            bridge.stabilize()

        self.renderer_mode = renderer_mode
        self.logger = logger or get_logger(__name__)
        self.config = config
        self._engine_strategies = {
            "cycles": CyclesRenderStrategy(),
            "eevee": EeveeRenderStrategy(),
            "workbench": WorkbenchRenderStrategy(),
        }
        self._configure_engine()

    def _configure_engine(self):
        """Standardizes engine-specific settings."""
        strategy = self._engine_strategies.get(self.renderer_mode, CyclesRenderStrategy())
        strategy.configure()

        if self.renderer_mode == "cycles" and self.config:
            # Apply CV-Safe Adaptive Sampling
            bridge.bproc.renderer.set_noise_threshold(self.config.noise_threshold)
            bridge.bproc.renderer.set_max_amount_of_samples(self.config.max_samples)

            # Apply Denoising with Albedo/Normal guidance
            if self.config.enable_denoising:
                self.logger.info(f"Enabling {self.config.denoiser_type} denoiser")
                bridge.bproc.renderer.set_denoiser(self.config.denoiser_type)

                if self.config.denoiser_type == "INTEL":
                    # Intel OIDN performs much better with Albedo and Normal guidance
                    # for preserving high-frequency edges like tag corners.
                    bridge.bproc.renderer.enable_diffuse_color_output()
                    bridge.bproc.renderer.enable_normals_output()

            # Apply CV-Safe Light Paths
            bridge.bproc.renderer.set_light_bounces(
                diffuse_bounces=self.config.diffuse_bounces,
                glossy_bounces=self.config.glossy_bounces,
                transmission_bounces=self.config.transmission_bounces,
                transparent_max_bounces=self.config.transparent_bounces,
                volume_bounces=0,  # Volumes are expensive and usually not needed for tags
                max_bounces=self.config.total_bounces,
            )
            # BlenderProc doesn't wrap caustics, set via bpy directly
            bridge.bpy.context.scene.cycles.caustics_reflective = self.config.enable_caustics
            bridge.bpy.context.scene.cycles.caustics_refractive = self.config.enable_caustics

        # Plumb CPU thread budget from environment if available
        # Set in render_tag.core.utils.get_subprocess_env
        thread_budget = os.environ.get("BLENDER_CPU_THREADS")
        if thread_budget and thread_budget.isdigit():
            t = int(thread_budget)
            self.logger.info(f"Setting Blender render threads to {t}")
            bridge.bpy.context.scene.render.threads_mode = "FIXED"
            bridge.bpy.context.scene.render.threads = t

    def reset_volatile_state(self):
        """Clears objects from the scene but keeps heavy environment assets."""
        global_pool.release_all()
        bridge.bproc.utility.reset_keyframes()

    def setup_world(self, world_recipe: dict[str, Any]):
        """Sets up HDRI, lighting, and environment."""
        hdri_path = world_recipe.get("background_hdri")
        if hdri_path and Path(hdri_path).is_file():
            setup_background(Path(hdri_path))

        # Handle Background Texture Plane
        texture_path = world_recipe.get("texture_path")
        if texture_path and world_recipe.get("use_nodes", True):
            # Use managed background plane from pool
            bg_plane = global_pool.get_background_plane()
            setup_floor_material(
                bg_plane,
                texture_path=texture_path,
                scale=world_recipe.get("texture_scale", 1.0),
                rotation=world_recipe.get("texture_rotation", 0.0),
            )

        setup_lighting(world_recipe.get("lights", []))

    def spawn_objects(self, object_recipes: list[dict[str, Any]]):
        """Creates subjects (tags, boards, etc.) using generic primitives.
        
        This method implements Scene Graph Deduplication: if a BOARD with a 
        composite texture is present, it suppresses the generation of individual
        TAG objects that would otherwise cause Z-fighting.
        """
        tag_objects = []
        
        # Check if any BOARD with a texture exists in the recipe
        has_composite_board = any(
            obj.get("type") == "BOARD" and obj.get("texture_path") 
            for obj in object_recipes
        )

        for obj_recipe in object_recipes:
            obj_type = obj_recipe["type"]
            
            # Suppress individual TAGs if a composite BOARD is handling the rendering
            if obj_type == "TAG" and has_composite_board:
                continue

            location = obj_recipe.get("location", [0, 0, 0])
            rotation = obj_recipe.get("rotation_euler", [0, 0, 0])
            scale = obj_recipe.get("scale", [1, 1, 1])
            texture_path = obj_recipe.get("texture_path")
            keypoints_3d = obj_recipe.get("keypoints_3d")
            forward_axis = obj_recipe.get("forward_axis")

            if obj_type == "TAG":
                props = obj_recipe["properties"]
                tag_obj = create_tag_plane(
                    props["tag_size"],
                    Path(texture_path) if texture_path else None,
                    props["tag_family"],
                    tag_id=props["tag_id"],
                    margin_bits=props.get("margin_bits", 0),
                    material_config=obj_recipe.get("material"),
                )
                tag_obj.blender_obj.pass_index = props["tag_id"] + 1
                tag_obj.set_location(location)
                tag_obj.set_rotation_euler(rotation)

                # Attach metadata
                if keypoints_3d:
                    tag_obj.blender_obj["keypoints_3d"] = keypoints_3d
                if forward_axis:
                    tag_obj.blender_obj["forward_axis"] = forward_axis
                tag_obj.blender_obj["tag_id"] = props["tag_id"]
                tag_obj.blender_obj["tag_family"] = props["tag_family"]
                tag_obj.blender_obj["type"] = "TAG"

                tag_objects.append(tag_obj)

            elif obj_type == "BOARD":
                board_cfg = obj_recipe.get("board")
                if texture_path and board_cfg:
                    # Generic High-Fidelity Subject Path (Single Plane)
                    # We use the board_cfg just to derive the size for legacy create_board_plane,
                    # but we should ideally just use the scale from recipe if compiler did its job.
                    width = scale[0]
                    height = scale[1]
                    # Note: compiler.py currently sets scale=[1,1,1] and expects create_board_plane
                    # to handle dimensions via width/height params.
                    # We'll stick to compiler's logic for now.
                    if isinstance(board_cfg, dict):
                        cols, rows = board_cfg.get("cols"), board_cfg.get("rows")
                        ms = board_cfg.get("marker_size")
                        if board_cfg.get("type") == "aprilgrid":
                            sqs = ms * (1.0 + board_cfg.get("spacing_ratio", 0.0))
                        else:
                            sqs = board_cfg.get("square_size", ms)
                        width, height = sqs * cols, sqs * rows

                    board_obj = create_board_plane(
                        width=width,
                        height=height,
                        texture_path=texture_path,
                        location=location,
                        rotation_euler=rotation,
                    )
                    board_obj.blender_obj["tag_family"] = "calibration_board"
                    import json

                    board_obj.blender_obj["board"] = json.dumps(board_cfg)
                    board_obj.blender_obj["type"] = "BOARD"
                else:
                    # Legacy or procedural board
                    props = obj_recipe.get("properties", {})
                    board_obj = create_board(
                        props.get("cols", 3),
                        props.get("rows", 3),
                        props.get("square_size", 0.1),
                        props.get("mode", "plain"),
                        location=location,
                    )
                    board_obj.blender_obj["tag_family"] = "legacy_board"
                    if rotation:
                        board_obj.set_rotation_euler(rotation)

                if keypoints_3d:
                    board_obj.blender_obj["keypoints_3d"] = keypoints_3d
                if forward_axis:
                    board_obj.blender_obj["forward_axis"] = forward_axis

                tag_objects.append(board_obj)
        return tag_objects

    def render_camera(self, camera_recipe: dict[str, Any]) -> dict[str, Any]:
        """Configures a camera and renders the image."""
        pose_matrix = bridge.np.array(camera_recipe["transform_matrix"])
        bridge.bproc.camera.add_camera_pose(pose_matrix, frame=0)
        setup_sensor_dynamics(pose_matrix, camera_recipe.get("sensor_dynamics"))

        # Apply intrinsics (Resolution, FOV, etc.)
        from render_tag.backend.camera import set_camera_intrinsics

        set_camera_intrinsics(camera_recipe)

        cam_data = bridge.bpy.context.scene.camera.data
        fstop = camera_recipe.get("fstop")
        if fstop:
            cam_data.dof.use_dof = True
            cam_data.dof.aperture_fstop = fstop
            focus_dist = camera_recipe.get("focus_distance")
            if focus_dist:
                cam_data.dof.focus_distance = focus_dist
        else:
            cam_data.dof.use_dof = False

        if bridge.bpy.context.scene.render.engine not in (
            "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT",
            "BLENDER_WORKBENCH",
        ):
            bridge.bproc.renderer.enable_segmentation_output(default_values={"category_id": 0})

        self.logger.info("Starting BlenderProc render call...")
        data = bridge.bproc.renderer.render()
        self.logger.info("BlenderProc render call completed.")
        img = data["colors"][0]

        if camera_recipe.get("sensor_noise"):
            img = apply_parametric_noise(img, camera_recipe["sensor_noise"])

        return {"img": img, "segmap": data.get("segmentation", [None])[0]}


def execute_recipe(
    recipe: dict[str, Any] | SceneRecipe,
    ctx: RenderContext,
    seed: int | None = None,
) -> None:
    """Execute a single scene recipe using the RenderContext."""
    # Staff Engineer: Normalize input to dictionary for uniform processing
    if hasattr(recipe, "model_dump"):
        # Pydantic model
        recipe_dict: Any = recipe.model_dump()  # type: ignore
    else:
        # Already a dict
        recipe_dict = recipe  # type: ignore

    scene_idx = recipe_dict["scene_id"]

    # 1. Setup Context-Aware Logger
    base_logger = ctx.logger or logger
    scene_logger = base_logger.bind(
        scene_id=scene_idx, seed=seed if seed is not None else scene_idx
    )
    scene_logger.info(f"--- Executing Scene {scene_idx} ---")

    # 2. Setup Scene
    renderer, tag_objects = _setup_scene(recipe_dict, ctx, scene_logger)

    cam_recipes = recipe_dict["cameras"]
    res = cam_recipes[0]["intrinsics"].get("resolution", [640, 480])

    provenance = {
        "git_hash": get_git_hash(),
        "timestamp": datetime.now(UTC).isoformat(),
        "recipe_snapshot": recipe_dict,
        "seeds": {
            "global_seed": ctx.global_seed,
            "scene_seed": recipe_dict.get("random_seed", 0),
        },
    }

    # 3. Render Cameras and Save Data
    for cam_idx, cam_recipe in enumerate(cam_recipes):
        coco_img_id, image_name = _render_camera_and_save(
            renderer, cam_idx, cam_recipe, recipe, ctx, scene_logger, provenance, res
        )

        _extract_and_save_ground_truth(tag_objects, image_name, coco_img_id, res, ctx, scene_logger)

        scene_logger.info(
            f"Scene {scene_idx} progress: {cam_idx + 1}/{len(cam_recipes)}",
            extra={
                "log_type": "progress",
                "payload": {
                    "current": cam_idx + 1,
                    "total": len(cam_recipes),
                    "scene_id": scene_idx,
                },
            },
        )

    scene_logger.info(f"✓ Rendered scene {scene_idx}")


def _setup_scene(
    recipe: dict[str, Any], ctx: RenderContext, scene_logger: Any
) -> tuple[RenderFacade, list[Any]]:
    """Initialize renderer, world, and spawn objects."""
    # All randomness is now resolved on the host side (Compiler).
    bridge.bpy.context.scene.cycles.use_animated_seed = False

    renderer_recipe = recipe.get("renderer", {})
    if isinstance(renderer_recipe, RendererConfig):
        renderer_config = renderer_recipe
    else:
        renderer_config = RendererConfig(**renderer_recipe)

    renderer = RenderFacade(
        renderer_mode=ctx.renderer_mode, logger=scene_logger, config=renderer_config
    )
    renderer.reset_volatile_state()
    renderer.setup_world(recipe.get("world", {}))
    tag_objects = renderer.spawn_objects(recipe.get("objects", []))

    for tag in tag_objects:
        family = tag.blender_obj.get("tag_family")
        if family:
            ctx.coco_writer.add_category(family)
        
        # If it's a BOARD, also register its specific marker dictionary
        if tag.blender_obj.get("type") == "BOARD":
            board_data = tag.blender_obj.get("board")
            if board_data:
                import json
                try:
                    config = json.loads(board_data) if isinstance(board_data, str) else board_data
                    dictionary = config.get("dictionary")
                    if dictionary:
                        ctx.coco_writer.add_category(dictionary)
                except (json.JSONDecodeError, AttributeError):
                    pass

    return renderer, tag_objects


def _render_camera_and_save(
    renderer: RenderFacade,
    cam_idx: int,
    cam_recipe: dict[str, Any],
    recipe: dict[str, Any],
    ctx: RenderContext,
    scene_logger: Any,
    provenance: dict[str, Any],
    res: list[int],
) -> tuple[int, str]:
    """Render a single camera view and save artifacts (image, sidecar)."""
    scene_idx = int(recipe["scene_id"])

    # Force subframe update for motion blur / consistency BEFORE render
    bridge.bpy.context.scene.frame_set(0, subframe=0.5)
    bridge.bpy.context.view_layer.update()

    start_time = time.time()
    render_out = renderer.render_camera(cam_recipe)
    render_time = time.time() - start_time

    scene_logger.info(
        f"Rendered camera {cam_idx}",
        extra={
            "log_type": "metric",
            "payload": {
                "metric": "render_time",
                "value": render_time,
                "unit": "seconds",
                "camera_idx": cam_idx,
            },
        },
    )

    image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
    image_path = ctx.output_dir / "images" / f"{image_name}.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)

    img_array = render_out.get("img")
    if img_array is not None and bridge.np.asarray(img_array).size > 0:
        Image.fromarray(bridge.np.asarray(img_array).astype(bridge.np.uint8)).save(str(image_path))

    ctx.sidecar_writer.write_sidecar(image_name, provenance)
    coco_img_id = ctx.coco_writer.add_image(f"images/{image_path.name}", res[0], res[1])

    return coco_img_id, image_name


def _extract_and_save_ground_truth(
    tag_objects: list[Any],
    image_name: str,
    coco_img_id: int,
    res: list[int],
    ctx: RenderContext,
    scene_logger: Any,
) -> None:
    """Project objects to image space and save detection records."""
    all_detections: list[DetectionRecord] = []
    from render_tag.backend.projection import generate_board_records, generate_subject_records

    for obj in tag_objects:
        obj_type = obj.blender_obj.get("type", "TAG")
        if obj_type == "BOARD":
            records = generate_board_records(obj, image_name, skip_visibility=ctx.skip_visibility)
        else:
            records = generate_subject_records(obj, image_name, skip_visibility=ctx.skip_visibility)
        
        all_detections.extend(records)

    # Save Ground Truth
    for det in all_detections:
        ctx.csv_writer.write_detection(det, res[0], res[1])
        ctx.coco_writer.add_annotation(
            image_id=coco_img_id,
            category_id=ctx.coco_writer.add_category(det.tag_family),
            corners=det.corners,
            width=res[0],
            height=res[1],
            detection=det,
        )
        ctx.rich_writer.add_detection(det)
