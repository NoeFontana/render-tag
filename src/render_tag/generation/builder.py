"""
Fluent Builder for Scene Recipes.

Provides a step-by-step interface for constructing complex SceneRecipe objects,
encapsulating the logic for isolated RNG states and component generation.
"""

import random
from typing import Any

import numpy as np

from render_tag.core import TAG_GRID_SIZES
from render_tag.core.config import TAG_MAX_IDS, GenConfig
from render_tag.data_io.assets import AssetProvider
from render_tag.generation.camera import sample_camera_pose
from render_tag.generation.layouts import apply_flying_layout, apply_grid_layout
from render_tag.core.schema import (
    CameraIntrinsics,
    CameraRecipe,
    LightingConfig,
    ObjectRecipe,
    SceneRecipe,
    SeedManager,
    SensorDynamicsRecipe,
    WorldRecipe,
)


class SceneRecipeBuilder:
    """
    Staff Engineer Pattern: Builder for SceneRecipes.
    Isolates the 'how' of construction from the 'what'.
    """

    def __init__(self, scene_id: int, config: GenConfig, asset_provider: AssetProvider):
        self.scene_id = scene_id
        self.config = config
        self.asset_provider = asset_provider
        self.recipe = SceneRecipe(scene_id=scene_id)

    def build_world(self, textures: list[Any]) -> "SceneRecipeBuilder":
        """Generates random world environment parameters."""
        # Use lighting seed for world randomization
        lighting_seed = self.config.dataset.seeds.lighting_seed
        seed = SeedManager(lighting_seed).get_shard_seed(self.scene_id)
        rng = random.Random(seed)
        
        scene_config = self.config.scene
        lighting_config = scene_config.lighting

        texture_path = None
        texture_scale = 1.0
        texture_rotation = 0.0

        if textures:
            # SHUFFLE the textures list deterministically based on lighting_seed 
            # to avoid every shard having the same texture for scene 0
            pool = list(textures)
            random.Random(lighting_seed).shuffle(pool)
            
            # Pick texture for this scene
            raw_path = str(pool[self.scene_id % len(pool)])
            texture_path = str(self.asset_provider.resolve_path(raw_path))
            texture_scale = rng.uniform(
                scene_config.texture_scale_min, scene_config.texture_scale_max
            )
            if scene_config.random_texture_rotation:
                texture_rotation = rng.uniform(0, 2 * np.pi)

        background_hdri = None
        if scene_config.background_hdri:
            background_hdri = str(
                self.asset_provider.resolve_path(str(scene_config.background_hdri))
            )

        self.recipe.world = WorldRecipe(
            background_hdri=background_hdri,
            lighting=LightingConfig(
                intensity=rng.uniform(lighting_config.intensity_min, lighting_config.intensity_max),
                radius=rng.uniform(lighting_config.radius_min, lighting_config.radius_max),
            ),
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )
        return self

    def build_objects(self) -> "SceneRecipeBuilder":
        """Generates and places tag objects within the scene."""
        seed = SeedManager(self.config.dataset.seeds.layout_seed).get_shard_seed(self.scene_id)
        rng = random.Random(seed)
        tag_config = self.config.tag
        scenario = self.config.scenario

        if scenario.layouts:
            layout_mode = scenario.layouts[self.scene_id % len(scenario.layouts)]
        else:
            layout_mode = scenario.layout

        objects = []
        grid_size = scenario.grid_size
        cols, rows = grid_size[0], grid_size[1]
        tag_size = tag_config.size_meters
        tag_families = [f.value for f in scenario.tag_families]

        if layout_mode == "cb":
            num_tags = (cols * rows + 1) // 2
        elif layout_mode == "aprilgrid":
            num_tags = cols * rows
        else:
            tags_range = scenario.tags_per_scene
            num_tags = rng.randint(tags_range[0], tags_range[1])

        for i in range(num_tags):
            family = rng.choice(tag_families)
            max_id = TAG_MAX_IDS.get(family, 100)
            tag_id = rng.randint(0, max_id - 1)

            tex_base = None
            if tag_config.texture_path:
                tex_base = str(self.asset_provider.resolve_path(str(tag_config.texture_path)))

            objects.append(
                ObjectRecipe(
                    type="TAG",
                    name=f"Tag_{i}",
                    location=[0, 0, 0],
                    rotation_euler=[0, 0, 0],
                    scale=[1, 1, 1],
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

        self.recipe.objects = objects
        return self

    def build_cameras(self) -> "SceneRecipeBuilder":
        """Generates multiple camera poses and sensor configurations."""
        seed = SeedManager(self.config.dataset.seeds.camera_seed).get_shard_seed(self.scene_id)
        np_rng = np.random.default_rng(seed)
        camera_config = self.config.camera
        scenario = self.config.scenario
        num_scenes = self.config.dataset.num_scenes

        # Get first tag for sizing constraints (typical for single-tag scenes)
        target_tag = None
        for obj in self.recipe.objects:
            if obj.type == "TAG":
                target_tag = obj
                break

        recipes = []
        for _ in range(camera_config.samples_per_scene):
            dist_override = None
            elev_override = None

            if num_scenes > 1:
                t = self.scene_id / (num_scenes - 1)
                if scenario.sampling_mode == "distance":
                    dist_override = camera_config.min_distance + t * (
                        camera_config.max_distance - camera_config.min_distance
                    )
                elif scenario.sampling_mode == "angle":
                    elev_override = camera_config.min_elevation + t * (
                        camera_config.max_elevation - camera_config.min_elevation
                    )

            # PPM Constraint Calculation
            if camera_config.ppm_constraint and target_tag:
                from render_tag.generation.projection_math import solve_distance_for_ppm
                
                # 1. Retrieve Tag Grid Size
                family = target_tag.properties.get("tag_family", "tag36h11")
                tag_grid_size = TAG_GRID_SIZES.get(family, 8)
                
                # 2. Calculate effective focal length
                width = camera_config.resolution[0]
                fov_rad = np.radians(camera_config.fov)
                f_px = width / (2.0 * np.tan(fov_rad / 2.0))
                
                # 3. Sample Target PPM
                target_ppm = np_rng.uniform(
                    camera_config.ppm_constraint.min,
                    camera_config.ppm_constraint.max
                )
                
                # 4. Solve for distance
                dist_override = solve_distance_for_ppm(
                    target_ppm=target_ppm,
                    tag_size_m=target_tag.properties.get("tag_size", 0.1),
                    focal_length_px=f_px,
                    tag_grid_size=tag_grid_size
                )

            # Rejection Sampling for Tag Size
            pose = None
            max_attempts = 20
            for attempt in range(max_attempts):
                # Sample roll if defined
                roll = 0.0
                if abs(camera_config.max_roll - camera_config.min_roll) > 1e-6:
                    roll = np_rng.uniform(
                        np.radians(camera_config.min_roll), 
                        np.radians(camera_config.max_roll)
                    )

                pose = sample_camera_pose(
                    look_at_point=[0, 0, 0],
                    min_distance=camera_config.min_distance,
                    max_distance=camera_config.max_distance,
                    min_elevation=camera_config.min_elevation,
                    max_elevation=camera_config.max_elevation,
                    azimuth=camera_config.azimuth,
                    distance=dist_override,
                    elevation=elev_override if elev_override is not None else camera_config.elevation,
                    inplane_rot=roll,
                    rng=np_rng,
                )

                # If we have a target tag and sizing constraints, validate area
                if target_tag and (camera_config.min_tag_pixels or camera_config.max_tag_pixels):
                    from render_tag.core.config import get_min_pixel_area
                    from render_tag.generation.projection_math import (
                        calculate_pixel_area,
                        get_world_matrix,
                        project_points,
                    )

                    # Projection logic
                    family = target_tag.properties.get("tag_family", "tag36h11")
                    min_allowed = camera_config.min_tag_pixels or get_min_pixel_area(family)
                    max_allowed = camera_config.max_tag_pixels or (camera_config.resolution[0] * camera_config.resolution[1])

                    size = target_tag.properties.get("tag_size", 0.1)
                    hs = size / 2.0
                    corners_local = np.array([[-hs, -hs, 0], [hs, -hs, 0], [hs, hs, 0], [-hs, hs, 0]])
                    tag_world_mat = get_world_matrix(target_tag.location, target_tag.rotation_euler, target_tag.scale)
                    corners_world_h = (tag_world_mat @ np.hstack([corners_local, np.ones((4, 1))]).T).T
                    corners_world = corners_world_h[:, :3]

                    pixels = project_points(
                        corners_world, 
                        pose.transform_matrix, 
                        list(camera_config.resolution), 
                        camera_config.fov
                    )
                    area = calculate_pixel_area(pixels)

                    if area >= min_allowed and area <= max_allowed:
                        break # Valid pose found
                    
                    if attempt == max_attempts - 1:
                        # Fallback to last pose if all attempts fail, but log warning
                        # or we could keep pose as None and handle it.
                        pass
                else:
                    break # No constraints, take first pose

            velocity = None
            if camera_config.velocity_mean > 0 or camera_config.velocity_std > 0:
                direction = np_rng.normal(size=3)
                norm = np.linalg.norm(direction)
                direction = direction / norm if norm > 1e-6 else np.array([0.0, 0.0, 1.0])
                magnitude = max(0.0, np_rng.normal(camera_config.velocity_mean, camera_config.velocity_std))
                velocity = (direction * magnitude).tolist()

            dynamics = SensorDynamicsRecipe(
                velocity=velocity,
                shutter_time_ms=camera_config.sensor_dynamics.shutter_time_ms,
                rolling_shutter_duration_ms=camera_config.sensor_dynamics.rolling_shutter_duration_ms,
            )

            recipes.append(
                CameraRecipe(
                    transform_matrix=pose.transform_matrix.tolist(),
                    intrinsics=CameraIntrinsics(
                        resolution=list(camera_config.resolution),
                        fov=camera_config.fov,
                        intrinsics=camera_config.intrinsics.model_dump(),
                    ),
                    sensor_dynamics=dynamics,
                    fstop=camera_config.fstop,
                    focus_distance=camera_config.focus_distance,
                    iso_noise=camera_config.iso_noise,
                    sensor_noise=camera_config.sensor_noise,
                    min_tag_pixels=camera_config.min_tag_pixels,
                    max_tag_pixels=camera_config.max_tag_pixels,
                )
            )
        self.recipe.cameras = recipes
        return self

    def get_result(self) -> SceneRecipe:
        return self.recipe
