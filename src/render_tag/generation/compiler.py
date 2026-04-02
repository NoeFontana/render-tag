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
from .math import look_at_rotation, make_transformation_matrix
from .strategy.factory import get_subject_strategy
from .visibility import is_facing_camera

if TYPE_CHECKING:
    from .strategy.base import SubjectStrategy


class SceneCompiler:
    """Compiles a high-level JobSpec/GenConfig into a list of rigid SceneRecipes.

    This class owns all randomness and ensures that the resulting recipes
    are purely execution-ready instructions for a "dumb" worker.

    Attributes:
        config: The generation configuration.
        global_seed: Master seed for deterministic derivations.
        output_dir: Path to storage for recipes and textures.
        asset_provider: Resolver for textures and HDRI environments.
        strategy: Current subject rendering strategy (e.g., TagStrategy).
    """

    def __init__(
        self,
        config: GenConfig,
        global_seed: int = 42,
        output_dir: Path | None = None,
        asset_provider: AssetProvider | None = None,
    ):
        self.config = config
        self.global_seed = global_seed
        self.output_dir = output_dir
        self.asset_provider = asset_provider or AssetProvider()

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
        from render_tag.generation.context import GenerationContext

        ctx = GenerationContext(
            gen_config=self.config, output_dir=self.output_dir or Path("output")
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
        """Compile a specific shard of scenes.

        Args:
            shard_index: The zero-based index of the current shard.
            total_shards: The total number of shards the job is split into.
            exclude_ids: Optional set of scene IDs to skip.

        Returns:
            A list of compiled SceneRecipe objects for this shard.
        """
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
        """Compile a single scene recipe with full determinism.

        Args:
            scene_id: The unique identifier for the scene.

        Returns:
            A fully resolved SceneRecipe with all randomness removed.
        """
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
        recipe.world = self._build_world_recipe(scene_id, world_seed)

        # 2. Objects (Agnostic Subject Generation)
        from render_tag.generation.context import GenerationContext

        ctx = GenerationContext(
            gen_config=self.config, output_dir=self.output_dir or Path("output")
        )

        objects = self.strategy.sample_pose(seed, ctx)
        recipe.objects = objects

        # 3. Cameras
        recipe.cameras = self._sample_camera_recipes(scene_id, seed, objects)

        return recipe

    def _build_world_recipe(self, scene_id: int, seed: int) -> WorldRecipe:
        """Build the world/environment part of the recipe."""
        rng = np.random.default_rng(seed)
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
            l_seed = derive_seed(seed, "light", l_idx)
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

        return WorldRecipe(
            background_hdri=background_hdri,
            lights=lights,
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )

    def _calculate_ppm_distance(self, target_tag, np_rng) -> float | None:
        """Calculate override distance for a target PPM."""
        from .projection_math import solve_distance_for_ppm

        camera_config = self.config.camera
        if not camera_config.ppm_constraint:
            return None

        f_px = camera_config.resolution[0] / (2.0 * np.tan(np.radians(camera_config.fov) / 2.0))
        target_ppm = np_rng.uniform(
            camera_config.ppm_constraint.min, camera_config.ppm_constraint.max
        )

        # Use active marker size (black border) for PPM calculation
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

        from render_tag.core.constants import TAG_GRID_SIZES

        return solve_distance_for_ppm(
            target_ppm=target_ppm,
            tag_size_m=tag_size_m,
            focal_length_px=f_px,
            tag_grid_size=TAG_GRID_SIZES.get(
                target_tag.properties.get("tag_family", "tag36h11"), 8
            ),
        )

    def _sample_single_pose(self, np_rng, dist_override, elev_override, target_tag):
        """Sample a single valid camera pose using rejection sampling."""
        camera_config = self.config.camera
        scenario = self.config.scenario

        # Staff Engineer: Use target tag location as look-at point in random mode to
        # ensure visibility.
        # In sweep modes, we look at the origin [0,0,0] to maintain the geometric contract
        # relative to the center of the world.
        if scenario.sampling_mode == "random" and target_tag:
            look_at = np.array(target_tag.location)
        else:
            look_at = np.array([0.0, 0.0, 0.0])

        for _ in range(50):  # Increased retries for better coverage of edge cases
            # 1. Determine camera location parameters
            dist = (
                dist_override
                if dist_override is not None
                else np_rng.uniform(camera_config.min_distance, camera_config.max_distance)
            )
            elev = (
                elev_override
                if elev_override is not None
                else (
                    camera_config.elevation
                    if camera_config.elevation is not None
                    else np_rng.uniform(camera_config.min_elevation, camera_config.max_elevation)
                )
            )
            azim = (
                camera_config.azimuth
                if camera_config.azimuth is not None
                else np_rng.uniform(0, 2 * np.pi)
            )

            # 2. Sample target position in image frame if in random mode
            target_image_pos = None
            if scenario.sampling_mode == "random" and target_tag:
                # Estimate tag angular size to define a safe sampling margin.
                # Max extent from center is diagonal: size * sqrt(2) / 2 approx 0.707 * size.
                # We use a 1.0x factor to be very safe against roll and perspective distortion.
                tag_size = target_tag.properties.get("tag_size", 0.1)
                if target_tag.type == "BOARD" and target_tag.board:
                    tag_size = max(
                        target_tag.board.cols * target_tag.board.marker_size,
                        target_tag.board.rows * target_tag.board.marker_size,
                    )

                f_px = camera_config.resolution[0] / (
                    2.0 * np.tan(np.radians(camera_config.fov) / 2.0)
                )
                pixel_margin = (f_px * tag_size) / dist

                w, h = camera_config.resolution
                if pixel_margin * 2 < min(w, h):
                    u = np_rng.uniform(pixel_margin, w - pixel_margin)
                    v = np_rng.uniform(pixel_margin, h - pixel_margin)
                    target_image_pos = np.array([u, v])

            # 3. Sample roll
            roll = (
                np_rng.uniform(
                    np.radians(camera_config.min_roll), np.radians(camera_config.max_roll)
                )
                if abs(camera_config.max_roll - camera_config.min_roll) > 1e-6
                else 0.0
            )

            # 4. Generate candidate pose
            pose = sample_camera_pose(
                look_at_point=look_at,
                distance=dist,
                elevation=elev,
                azimuth=azim,
                inplane_rot=roll,
                target_image_pos=target_image_pos,
                k_matrix=camera_config.get_k_matrix(),
                rng=np_rng,
            )

            # 5. Validate all constraints
            if self._validate_pose_constraints(pose, target_tag):
                return pose

        return None

    def _sample_camera_recipes(self, scene_id: int, seed: int, objects: list) -> list[CameraRecipe]:
        """Sample multiple camera poses and create recipes."""
        camera_seed = derive_seed(seed, "camera", 0)
        np_rng = np.random.default_rng(camera_seed)
        camera_config = self.config.camera
        sequence_config = self.config.sequence

        # Find potential targets for orientation/sizing constraints
        # Prefer actual TAGs, fallback to any object
        all_tags = [obj for obj in objects if obj.type == "TAG"]
        if sequence_config.enabled:
            if not objects:
                raise ValueError("Sequence mode requires at least one object to track.")
            sequence_target = all_tags[0] if all_tags else objects[0]
            return self._sample_sequence_camera_recipes(
                scene_id=scene_id,
                camera_seed=camera_seed,
                np_rng=np_rng,
                target_tag=sequence_target,
            )

        camera_recipes = []
        for cam_idx in range(camera_config.samples_per_scene):
            target_tag = None
            if all_tags:
                target_tag = np_rng.choice(all_tags)
            elif objects:
                target_tag = objects[0]

            pose = self._sample_pose_for_index(scene_id, np_rng, target_tag)
            camera_recipes.append(
                self._build_camera_recipe(
                    pose=pose,
                    cam_idx=cam_idx,
                    camera_seed=camera_seed,
                )
            )
        return camera_recipes

    def _sample_pose_for_index(self, scene_id: int, np_rng, target_tag):
        """Sample a valid pose for a camera index using current sweep settings."""
        camera_config = self.config.camera
        scenario = self.config.scenario

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

        if scenario.sampling_mode == "random" and camera_config.ppm_constraint and target_tag:
            dist_override = self._calculate_ppm_distance(target_tag, np_rng)
            if dist_override is not None:
                dist_override = np.clip(
                    dist_override, camera_config.min_distance, camera_config.max_distance
                )

        pose = self._sample_single_pose(np_rng, dist_override, elev_override, target_tag)
        if not pose:
            raise ValueError(
                f"Failed to sample a valid camera pose for scene {scene_id} "
                f"after 20 attempts with constraints."
            )
        return pose

    def _build_camera_recipe(
        self,
        pose,
        cam_idx: int,
        camera_seed: int,
        *,
        velocity: list[float] | None = None,
        frame_index: int | None = None,
        timestamp_s: float | None = None,
        sequence_pose_delta: list[float] | None = None,
    ) -> CameraRecipe:
        """Build a camera recipe with consistent intrinsics and sensor metadata."""
        camera_config = self.config.camera
        sensor_config = camera_config.sensor_dynamics

        if velocity is None and (camera_config.velocity_mean > 0 or camera_config.velocity_std > 0):
            np_rng = np.random.default_rng(derive_seed(camera_seed, "velocity", cam_idx))
            direction = np_rng.normal(size=3)
            norm = np.linalg.norm(direction)
            direction = direction / norm if norm > 1e-6 else np.array([0.0, 0.0, 1.0])
            magnitude = max(
                0.0, np_rng.normal(camera_config.velocity_mean, camera_config.velocity_std)
            )
            velocity = (direction * magnitude).tolist()

        if camera_config.sensor_noise:
            noise_recipe = camera_config.sensor_noise.model_dump()
            noise_recipe["seed"] = derive_seed(camera_seed, "noise", cam_idx)
        else:
            noise_recipe = None

        rolling_shutter_ms = sensor_config.rolling_shutter_duration_ms
        if sensor_config.blur_profile == "light":
            rolling_shutter_ms = 0.0

        return CameraRecipe(
            transform_matrix=pose.transform_matrix.tolist(),
            intrinsics=CameraIntrinsics(
                resolution=list(camera_config.resolution),
                k_matrix=camera_config.get_k_matrix(),
                fov=camera_config.fov,
            ),
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            sequence_pose_delta=sequence_pose_delta,
            sensor_dynamics=SensorDynamicsRecipe(
                blur_profile=sensor_config.blur_profile,
                velocity=velocity,
                shutter_time_ms=sensor_config.shutter_time_ms,
                rolling_shutter_duration_ms=rolling_shutter_ms,
            ),
            fstop=camera_config.fstop,
            focus_distance=camera_config.focus_distance,
            min_tag_pixels=camera_config.min_tag_pixels,
            max_tag_pixels=camera_config.max_tag_pixels,
            iso_noise=camera_config.iso_noise,
            sensor_noise=noise_recipe,
        )

    def _sample_sequence_camera_recipes(
        self,
        scene_id: int,
        camera_seed: int,
        np_rng: np.random.Generator,
        target_tag,
    ) -> list[CameraRecipe]:
        """Generate a temporally coherent sequence of nearby camera poses."""
        sequence_config = self.config.sequence
        base_pose = self._sample_pose_for_index(scene_id, np_rng, target_tag)
        target_location = np.array(
            target_tag.location if target_tag else [0.0, 0.0, 0.0],
            dtype=float,
        )

        locations = self._sample_sequence_locations(
            base_location=base_pose.location,
            target_location=target_location,
            frames_per_sequence=sequence_config.frames_per_sequence,
            np_rng=np_rng,
        )

        poses = []
        for location in locations:
            forward_vec = target_location - location
            rotation_matrix = look_at_rotation(forward_vec)
            transform_matrix = make_transformation_matrix(location, rotation_matrix)
            pose = type(base_pose)(
                location=location,
                rotation_matrix=rotation_matrix,
                transform_matrix=transform_matrix,
            )
            if not self._validate_pose_constraints(pose, target_tag):
                raise ValueError(
                    f"Failed to generate a valid sequence pose for scene {scene_id} "
                    "under the current motion limits."
                )
            poses.append(pose)

        camera_recipes: list[CameraRecipe] = []
        dt = 1.0 / float(sequence_config.fps)
        shutter_midpoint_offset_s = (
            float(self.config.camera.sensor_dynamics.shutter_time_ms or 0.0) / 2000.0
        )
        for cam_idx, pose in enumerate(poses):
            if cam_idx == 0:
                delta = np.zeros(3, dtype=float)
                velocity = [0.0, 0.0, 0.0]
            else:
                delta = pose.location - poses[cam_idx - 1].location
                velocity = (delta / dt).tolist()

            camera_recipes.append(
                self._build_camera_recipe(
                    pose=pose,
                    cam_idx=cam_idx,
                    camera_seed=camera_seed,
                    velocity=velocity,
                    frame_index=cam_idx,
                    timestamp_s=(cam_idx * dt) + shutter_midpoint_offset_s,
                    sequence_pose_delta=delta.tolist(),
                )
            )
        return camera_recipes

    def _sample_sequence_locations(
        self,
        base_location: np.ndarray,
        target_location: np.ndarray,
        frames_per_sequence: int,
        np_rng: np.random.Generator,
    ) -> list[np.ndarray]:
        """Sample smooth nearby camera locations for a natural-robot trajectory."""
        sequence_config = self.config.sequence
        camera_config = self.config.camera

        start_offset = base_location - target_location
        radius = float(np.linalg.norm(start_offset))
        if radius < 1e-6:
            raise ValueError("Sequence mode requires a non-degenerate base camera radius.")

        radial_dir = start_offset / radius
        world_up = np.array([0.0, 0.0, 1.0], dtype=float)
        lateral_dir = np.cross(world_up, radial_dir)
        lateral_norm = np.linalg.norm(lateral_dir)
        if lateral_norm < 1e-6:
            lateral_dir = np.array([1.0, 0.0, 0.0], dtype=float)
        else:
            lateral_dir /= lateral_norm
        vertical_dir = np.cross(radial_dir, lateral_dir)
        vertical_dir /= np.linalg.norm(vertical_dir)

        pattern = np_rng.choice(["straight", "diagonal", "arc"])
        max_step = min(
            sequence_config.max_translation_per_frame_m,
            max(0.0, (camera_config.max_distance - camera_config.min_distance) / 4.0),
        )
        step_scale = np_rng.uniform(0.35, 1.0) * max_step
        if pattern == "straight":
            motion_dir = lateral_dir if np_rng.random() < 0.5 else vertical_dir
        elif pattern == "diagonal":
            motion_dir = lateral_dir + np_rng.choice([-1.0, 1.0]) * 0.5 * vertical_dir
            motion_dir /= np.linalg.norm(motion_dir)
        else:
            motion_dir = lateral_dir

        center = (frames_per_sequence - 1) / 2.0
        locations = []
        for frame_idx in range(frames_per_sequence):
            offset_scalar = (frame_idx - center) * step_scale
            location = base_location + motion_dir * offset_scalar
            if pattern == "arc":
                yaw_total_deg = (frame_idx - center) * sequence_config.max_yaw_deg_per_frame
                yaw_rad = np.radians(yaw_total_deg)
                cos_yaw = np.cos(yaw_rad)
                sin_yaw = np.sin(yaw_rad)
                rotated_radial = (cos_yaw * radial_dir) + (sin_yaw * lateral_dir)
                rotated_radial /= np.linalg.norm(rotated_radial)
                location = (
                    target_location + rotated_radial * radius + vertical_dir * offset_scalar * 0.25
                )
            distance = np.linalg.norm(location - target_location)
            location = target_location + ((location - target_location) / distance) * np.clip(
                distance, camera_config.min_distance, camera_config.max_distance
            )
            locations.append(location)
        return locations

    def _validate_pose_constraints(self, pose, target_tag) -> bool:
        """Validate orientation and sizing constraints for a sampled pose."""
        if not target_tag:
            return True

        from ..core.config import get_min_pixel_area
        from .projection_math import (
            calculate_pixel_area,
            get_world_matrix,
            project_points,
        )

        camera_config = self.config.camera

        # 1. Orientation check
        tag_world_mat = get_world_matrix(
            target_tag.location, target_tag.rotation_euler, target_tag.scale
        )
        tag_normal = tag_world_mat[:3, 2]  # Z-up normal
        if not is_facing_camera(
            tag_location=np.array(target_tag.location),
            tag_normal=tag_normal,
            camera_location=pose.location,
            min_dot=0.1,  # Relaxed to ~84 degrees to support low-elevation tests/views
        ):
            return False

        # 2. Mandatory Frame Visibility check
        # All 4 corners of the tag (or target object) must be within the frame
        if target_tag.type == "BOARD" and target_tag.board:
            # Rigid Calibration Board (Strategy uses scale in recipe)
            hw, hh = 0.5, 0.5
        elif target_tag.type == "BOARD":
            # Background Board (TagStrategy uses unit scale in recipe)
            cols = target_tag.properties.get("cols", 1)
            rows = target_tag.properties.get("rows", 1)
            sq = target_tag.properties.get("square_size", 0.1)
            hw = (cols * sq) / 2.0
            hh = (rows * sq) / 2.0
        else:
            # Individual Tag
            size = target_tag.properties.get("tag_size", 0.1)
            hw = hh = size / 2.0

        corners_local = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]])
        corners_world = (tag_world_mat @ np.hstack([corners_local, np.ones((4, 1))]).T).T[:, :3]
        pixels = project_points(
            corners_world,
            pose.transform_matrix,
            list(camera_config.resolution),
            camera_config.get_k_matrix(),
        )

        # Strict boundary check (all corners must be visible)
        if not all(
            0 <= px <= camera_config.resolution[0] and 0 <= py <= camera_config.resolution[1]
            for px, py in pixels
        ):
            return False

        # 3. Optional Sizing constraints validation (Pixel Area)
        if camera_config.min_tag_pixels or camera_config.max_tag_pixels:
            family = target_tag.properties.get("tag_family", "tag36h11")
            min_allowed = camera_config.min_tag_pixels or get_min_pixel_area(family)
            max_allowed = camera_config.max_tag_pixels or (
                camera_config.resolution[0] * camera_config.resolution[1]
            )

            if not (min_allowed <= calculate_pixel_area(pixels) <= max_allowed):
                return False

        return True
