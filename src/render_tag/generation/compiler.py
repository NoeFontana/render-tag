
"""
Deterministic Scene Compiler for render-tag.

Shifts all "decision-making" (random sampling, asset selection, pose calculation)
from the Blender runtime to the pure-Python preparation phase.
"""

import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ..core.config import GenConfig
from ..core.constants import TAG_GRID_SIZES
from ..core.schema import (
    CameraIntrinsics,
    CameraRecipe,
    LightRecipe,
    SceneRecipe,
    SensorDynamicsRecipe,
    WorldRecipe,
)
from ..core.seeding import derive_seed
from ..data_io.assets import AssetProvider
from .camera import sample_camera_pose
from .strategy.factory import get_subject_strategy
from .visibility import is_facing_camera

if TYPE_CHECKING:
    from .strategy.base import SubjectStrategy


class SceneCompiler:
    """
    Compiles a high-level JobSpec/GenConfig into a list of rigid SceneRecipes.

    This class owns all randomness and ensures that the resulting recipes
    are purely execution-ready instructions for a "dumb" worker.
    """

    def __init__(
        self,
        config: GenConfig,
        global_seed: int = 42,
        output_dir: Path | None = None,
    ):
        self.config = config
        self.global_seed = global_seed
        self.output_dir = output_dir
        self.asset_provider = AssetProvider()

        # Initialize Subject Strategy
        self.strategy: SubjectStrategy = get_subject_strategy(self.config.scenario.subject)
        
        # If it's a TagStrategy, we might need to synchronize its config with GenConfig
        # (Though ideally SubjectConfig should already be correct)
        from .strategy.tags import TagStrategy
        if isinstance(self.strategy, TagStrategy):
            # Update strategy config to match GenConfig if needed
            # For now, we assume SubjectConfig is the source of truth for the strategy
            pass

        # Prepare assets for the subject once per compiler instance
        from render_tag.cli.pipeline import GenerationContext
        ctx = GenerationContext(
            gen_config=self.config,
            output_dir=self.output_dir or Path("output")
        )
        self.strategy.prepare_assets(ctx)

        # Cache textures
        self.textures = []
        if self.config.scene.texture_dir and self.config.scene.texture_dir.exists():
            valid_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            self.textures = [
                p
                for p in self.config.scene.texture_dir.rglob("*")
                if p.suffix.lower() in valid_exts
            ]

    def compile_shards(
        self,
        shard_index: int,
        total_shards: int,
        exclude_ids: set[int] | None = None,
    ) -> list[SceneRecipe]:
        """Compile a specific shard of scenes."""
        exclude_ids = exclude_ids or set()
        total_scenes = self.config.dataset.num_scenes

        if total_shards > total_scenes:
            total_shards = total_scenes
            if shard_index >= total_shards:
                return []

        scenes_per_shard = total_scenes // total_shards
        start_idx = shard_index * scenes_per_shard
        end_idx = total_scenes if shard_index == total_shards - 1 else start_idx + scenes_per_shard

        recipes = []
        for i in range(start_idx, end_idx):
            if i in exclude_ids:
                continue
            recipes.append(self.compile_scene(i))
        return recipes

    def compile_scene(self, scene_id: int) -> SceneRecipe:
        """Compile a single scene recipe with full determinism."""
        # Derive Scene Seed
        scene_seed = derive_seed(self.global_seed, "scene", scene_id)

        # We might need to retry if validation fails (handled by Generator/caller)
        # but the Compiler itself should be deterministic for a given seed.
        return self._build_recipe(scene_id, scene_seed)

    def _build_recipe(self, scene_id: int, seed: int) -> SceneRecipe:
        """Internal build logic that resolves all ranges into absolute values."""
        recipe = SceneRecipe(
            scene_id=scene_id,
            random_seed=seed,
            renderer=self.config.renderer,
        )

        # 1. World
        world_seed = derive_seed(seed, "world", 0)
        rng = np.random.default_rng(world_seed)

        scene_config = self.config.scene
        lighting_config = scene_config.lighting

        texture_path = None
        texture_scale = 1.0
        texture_rotation = 0.0

        if self.textures:
            pool = list(self.textures)
            rng.shuffle(pool)
            raw_path = str(pool[scene_id % len(pool)])
            texture_path = str(self.asset_provider.resolve_path(raw_path).absolute())

            min_s = scene_config.texture_scale_min
            max_s = scene_config.texture_scale_max
            if max_s / min_s > 10.0:
                log_min = math.log(min_s)
                log_max = math.log(max_s)
                texture_scale = math.exp(rng.uniform(log_min, log_max))
            else:
                texture_scale = rng.uniform(min_s, max_s)

            if scene_config.random_texture_rotation:
                texture_rotation = rng.uniform(0, 2 * np.pi)

        background_hdri = None
        if scene_config.background_hdri:
            background_hdri = str(
                self.asset_provider.resolve_path(str(scene_config.background_hdri)).absolute()
            )

        num_lights = 3
        lights = []
        for l_idx in range(num_lights):
            # Deterministic light positions
            l_seed = derive_seed(world_seed, "light", l_idx)
            l_rng = np.random.default_rng(l_seed)

            theta = l_rng.uniform(0, 2 * math.pi)
            phi = l_rng.uniform(0.2, 0.8) * math.pi / 2
            radius = l_rng.uniform(2, 5)

            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)

            intensity = (
                l_rng.uniform(lighting_config.intensity_min, lighting_config.intensity_max)
                / num_lights
            )

            lights.append(
                LightRecipe(
                    location=[x, y, z],
                    intensity=intensity,
                    radius=l_rng.uniform(lighting_config.radius_min, lighting_config.radius_max),
                    color=[1.0, 1.0, 1.0],
                )
            )

        recipe.world = WorldRecipe(
            background_hdri=background_hdri,
            lights=lights,
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )

        # 2. Objects (Agnostic Subject Generation)
        from render_tag.cli.pipeline import GenerationContext
        ctx = GenerationContext(
            gen_config=self.config,
            output_dir=self.output_dir or Path("output")
        )
        
        objects = self.strategy.sample_pose(seed, ctx)
        recipe.objects = objects

        # 3. Cameras
        camera_seed = derive_seed(seed, "camera", 0)
        np_rng = np.random.default_rng(camera_seed)
        camera_config = self.config.camera
        scenario = self.config.scenario

        # Find target for orientation/sizing constraints
        # 1. Prefer an actual TAG
        target_tag = next((obj for obj in objects if obj.type == "TAG"), None)
        # 2. Fallback to any object if no TAG found (e.g. BOARD subject)
        if not target_tag and objects:
            target_tag = objects[0]
            
        camera_recipes = []

        for _ in range(camera_config.samples_per_scene):
            dist_override = None
            elev_override = None

            if self.config.dataset.num_scenes > 1:
                t = scene_id / (self.config.dataset.num_scenes - 1)
                if scenario.sampling_mode == "distance":
                    dist_override = camera_config.min_distance + t * (
                        camera_config.max_distance - camera_config.min_distance
                    )
                elif scenario.sampling_mode == "angle":
                    elev_override = camera_config.min_elevation + t * (
                        camera_config.max_elevation - camera_config.min_elevation
                    )

            if camera_config.ppm_constraint and target_tag:
                from .projection_math import solve_distance_for_ppm

                f_px = camera_config.resolution[0] / (
                    2.0 * np.tan(np.radians(camera_config.fov) / 2.0)
                )
                target_ppm = np_rng.uniform(
                    camera_config.ppm_constraint.min, camera_config.ppm_constraint.max
                )
                
                # Use active marker size (black border) for PPM calculation, not total plane size
                tag_size_m = target_tag.properties.get("tag_size", 0.1)
                if target_tag.type == "TAG":
                    from render_tag.core.constants import TAG_GRID_SIZES
                    family = target_tag.properties.get("tag_family", "tag36h11")
                    margin_bits = target_tag.properties.get("margin_bits", 0)
                    grid_size = TAG_GRID_SIZES.get(family, 8)
                    total_bits = grid_size + (2 * margin_bits)
                    tag_size_m = tag_size_m * (grid_size / total_bits)
                elif target_tag.type == "BOARD" and target_tag.board:
                    tag_size_m = target_tag.board.marker_size
                
                dist_override = solve_distance_for_ppm(
                    target_ppm=target_ppm,
                    tag_size_m=tag_size_m,
                    focal_length_px=f_px,
                    tag_grid_size=TAG_GRID_SIZES.get(
                        target_tag.properties.get("tag_family", "tag36h11"), 8
                    ),
                )

            pose = None
            for _ in range(20):  # Rejection sampling
                roll = (
                    np_rng.uniform(
                        np.radians(camera_config.min_roll), np.radians(camera_config.max_roll)
                    )
                    if abs(camera_config.max_roll - camera_config.min_roll) > 1e-6
                    else 0.0
                )
                pose = sample_camera_pose(
                    look_at_point=[0, 0, 0],
                    min_distance=camera_config.min_distance,
                    max_distance=camera_config.max_distance,
                    min_elevation=camera_config.min_elevation,
                    max_elevation=camera_config.max_elevation,
                    azimuth=camera_config.azimuth,
                    distance=dist_override,
                    elevation=elev_override
                    if elev_override is not None
                    else camera_config.elevation,
                    inplane_rot=roll,
                    rng=np_rng,
                )

                # Sizing and Orientation constraints validation...
                if target_tag:
                    from ..core.config import get_min_pixel_area
                    from .projection_math import (
                        calculate_pixel_area,
                        get_world_matrix,
                        project_points,
                    )

                    # 1. Orientation check (Staff Pattern: reject if facing away)
                    tag_world_mat = get_world_matrix(
                        target_tag.location, target_tag.rotation_euler, target_tag.scale
                    )
                    tag_normal = tag_world_mat[:3, 2]  # Z-up normal
                    if not is_facing_camera(
                        tag_location=np.array(target_tag.location),
                        tag_normal=tag_normal,
                        camera_location=pose.location,
                        min_dot=0.2,  # ~78 degrees
                    ):
                        continue

                    # 2. Sizing constraints validation...
                    if camera_config.min_tag_pixels or camera_config.max_tag_pixels:
                        family = target_tag.properties.get("tag_family", "tag36h11")
                        min_allowed = camera_config.min_tag_pixels or get_min_pixel_area(family)
                        max_allowed = camera_config.max_tag_pixels or (
                            camera_config.resolution[0] * camera_config.resolution[1]
                        )

                        # Bounding box for sizing check
                        # If board, we use the whole board plane or just markers? 
                        # Specification says "sizing constraints validation". 
                        # We'll use marker size for boards.
                        check_size = target_tag.properties.get("tag_size", 0.1)
                        if target_tag.type == "BOARD" and target_tag.board:
                            check_size = target_tag.board.marker_size
                            
                        half = check_size / 2.0
                        corners_local = np.array(
                            [[-half, -half, 0], [half, -half, 0], [half, half, 0], [-half, half, 0]]
                        )
                        corners_world = (
                            tag_world_mat @ np.hstack([corners_local, np.ones((4, 1))]).T
                        ).T[:, :3]
                        pixels = project_points(
                            corners_world,
                            pose.transform_matrix,
                            list(camera_config.resolution),
                            camera_config.get_k_matrix(),
                        )

                        if not (
                            all(
                                0 <= px <= camera_config.resolution[0]
                                and 0 <= py <= camera_config.resolution[1]
                                for px, py in pixels
                            )
                            and min_allowed <= calculate_pixel_area(pixels) <= max_allowed
                        ):
                            continue

                    # If we reached here, both orientation and (optional) sizing passed
                    break
                else:
                    break

            velocity = None
            if camera_config.velocity_mean > 0 or camera_config.velocity_std > 0:
                direction = np_rng.normal(size=3)
                norm = np.linalg.norm(direction)
                direction = direction / norm if norm > 1e-6 else np.array([0.0, 0.0, 1.0])
                magnitude = max(
                    0.0, np_rng.normal(camera_config.velocity_mean, camera_config.velocity_std)
                )
                velocity = (direction * magnitude).tolist()

            if camera_config.sensor_noise:
                noise_recipe = camera_config.sensor_noise.model_dump()
                # Derive a deterministic seed for this specific camera's noise
                noise_recipe["seed"] = derive_seed(camera_seed, "noise", _)
            else:
                noise_recipe = None

            camera_recipes.append(
                CameraRecipe(
                    transform_matrix=pose.transform_matrix.tolist(),
                    intrinsics=CameraIntrinsics(
                        resolution=list(camera_config.resolution),
                        k_matrix=camera_config.get_k_matrix(),
                        fov=camera_config.fov,
                    ),
                    sensor_dynamics=SensorDynamicsRecipe(
                        velocity=velocity,
                        shutter_time_ms=camera_config.sensor_dynamics.shutter_time_ms,
                        rolling_shutter_duration_ms=camera_config.sensor_dynamics.rolling_shutter_duration_ms,
                    ),
                    fstop=camera_config.fstop,
                    focus_distance=camera_config.focus_distance,
                    min_tag_pixels=camera_config.min_tag_pixels,
                    max_tag_pixels=camera_config.max_tag_pixels,
                    iso_noise=camera_config.iso_noise,
                    sensor_noise=noise_recipe,
                )
            )
        recipe.cameras = camera_recipes
        return recipe
