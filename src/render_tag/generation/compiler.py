"""
Deterministic Scene Compiler for render-tag.

Shifts all "decision-making" (random sampling, asset selection, pose calculation)
from the Blender runtime to the pure-Python preparation phase.
"""

import math
from pathlib import Path

import numpy as np

from ..core.config import TAG_MAX_IDS, GenConfig
from ..core.constants import TAG_GRID_SIZES
from ..core.schema import (
    BoardConfig,
    CameraIntrinsics,
    CameraRecipe,
    LightRecipe,
    ObjectRecipe,
    SceneRecipe,
    SensorDynamicsRecipe,
    WorldRecipe,
)
from ..core.seeding import derive_seed
from ..data_io.assets import AssetProvider
from .camera import sample_camera_pose
from .layouts import apply_flying_layout, apply_grid_layout
from .texture_factory import TextureFactory
from .visibility import is_facing_camera


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

        # 2. Objects
        layout_seed = derive_seed(seed, "layout", 0)
        rng = np.random.default_rng(layout_seed)

        tag_config = self.config.tag
        scenario = self.config.scenario

        layout_mode = (
            scenario.layouts[scene_id % len(scenario.layouts)]
            if scenario.layouts
            else scenario.layout
        )

        objects = []
        cols, rows = scenario.grid_size[0], scenario.grid_size[1]
        tag_size = tag_config.size_meters
        tag_families = [f.value for f in scenario.tag_families]

        if layout_mode == "board":
            # High-Fidelity Calibration Board (Single Texture)
            if not scenario.board:
                raise ValueError("scenario.board config is required for 'board' layout mode")
            
            board_config = scenario.board
            
            # Use TextureFactory to generate/ensure board texture
            cache_dir = self.output_dir / "cache" / "boards" if self.output_dir else None
            factory = TextureFactory(cache_dir=cache_dir)
            # This will generate the texture and save it to cache
            img = factory.generate_board_texture(board_config)
            
            # Resolve texture path
            texture_path = None
            if cache_dir:
                config_hash = factory._calculate_hash(board_config)
                texture_path = str((cache_dir / f"board_{config_hash}.png").absolute())

            objects.append(
                ObjectRecipe(
                    type="BOARD",
                    name="CalibrationBoard",
                    location=[0, 0, 0],
                    rotation_euler=[0, 0, 0],
                    scale=[1, 1, 1],
                    texture_path=texture_path,
                    board=board_config,
                )
            )
        elif layout_mode == "cb":
            num_tags = (cols * rows + 1) // 2
        elif layout_mode == "aprilgrid":
            num_tags = cols * rows
        else:
            num_tags = int(
                rng.integers(scenario.tags_per_scene[0], scenario.tags_per_scene[1], endpoint=True)
            )

        for i in range(num_tags):
            obj_seed = derive_seed(layout_seed, "tag_obj", i)
            obj_rng = np.random.default_rng(obj_seed)

            family = obj_rng.choice(tag_families)
            max_id = TAG_MAX_IDS.get(family, 100)
            tag_id = int(obj_rng.integers(0, max_id))

            tex_base = None
            if tag_config.texture_path:
                tex_base = str(
                    self.asset_provider.resolve_path(str(tag_config.texture_path)).absolute()
                )

            # Resolve tag material properties here (Move-Left)
            roughness = 0.8
            specular = 0.2
            if tag_config.material and tag_config.material.randomize:
                roughness = obj_rng.uniform(
                    tag_config.material.roughness_min, tag_config.material.roughness_max
                )
                specular = obj_rng.uniform(
                    tag_config.material.specular_min, tag_config.material.specular_max
                )

            # Resolve texture path to the cache directory if output_dir is known
            texture_path = None
            if self.output_dir:
                margin_bits = tag_config.margin_bits
                texture_path = str(
                    (
                        self.output_dir / "cache" / "tags" / f"{family}_{tag_id}_m{margin_bits}.png"
                    ).absolute()
                )

            objects.append(
                ObjectRecipe(
                    type="TAG",
                    name=f"Tag_{i}",
                    location=[0, 0, 0],
                    rotation_euler=[0, 0, 0],
                    scale=[1, 1, 1],
                    texture_path=texture_path,
                    material={
                        "roughness": roughness,
                        "specular": specular,
                    },
                    properties={
                        "tag_id": tag_id,
                        "tag_family": family,
                        "tag_size": tag_size,
                        "margin_bits": tag_config.margin_bits,
                        "texture_base_path": tex_base,
                    },
                )
            )

        if scenario.flying:
            apply_flying_layout(objects, self.config.physics.scatter_radius, rng=rng)
        else:
            apply_grid_layout(
                objects,
                layout_mode,
                cols,
                rows,
                tag_size,
                tag_spacing_bits=scenario.tag_spacing_bits or 2.0,
                tag_families=tag_families,
            )
            if layout_mode in ("cb", "aprilgrid", "plain"):
                primary_family = tag_families[0]
                tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
                tag_spacing = (scenario.tag_spacing_bits / tag_bit_grid_size) * tag_size
                square_size = tag_size + tag_spacing
                if scenario.use_board:
                    objects.append(
                        ObjectRecipe(
                            type="BOARD",
                            name="Board_Background",
                            location=[0, 0, -0.005],
                            rotation_euler=[0, 0, 0],
                            scale=[1, 1, 1],
                            properties={
                                "mode": layout_mode,
                                "cols": cols,
                                "rows": rows,
                                "tag_size": tag_size,
                                "square_size": square_size,
                            },
                        )
                    )
        recipe.objects = objects

        # 3. Cameras
        camera_seed = derive_seed(seed, "camera", 0)
        np_rng = np.random.default_rng(camera_seed)
        camera_config = self.config.camera

        target_tag = next((obj for obj in objects if obj.type == "TAG"), None)
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
                dist_override = solve_distance_for_ppm(
                    target_ppm=target_ppm,
                    tag_size_m=target_tag.properties.get("tag_size", 0.1),
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

                        corners_local = np.array(
                            [[-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, 0.5, 0], [-0.5, 0.5, 0]]
                        ) * target_tag.properties.get("tag_size", 0.1)
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
