"""
Scene Generator for render-tag.

Initializes scene configurations and generates "Recipes" that can be executed
by a separate Blender process. This isolates logical calculations from Blender.
"""

import json
import random
from pathlib import Path
from typing import Any

import numpy as np

from render_tag.common import TAG_GRID_SIZES
from render_tag.common.logging import get_logger
from render_tag.schema import SeedManager
from render_tag.core.config import GenConfig
from render_tag.data_io.assets import AssetProvider
from render_tag.geometry.camera import sample_camera_pose
from render_tag.geometry.layouts import apply_flying_layout, apply_grid_layout
from render_tag.schema import (
    CameraIntrinsics,
    CameraRecipe,
    LightingConfig,
    ObjectRecipe,
    SceneRecipe,
    SensorDynamicsRecipe,
    WorldRecipe,
)

logger = get_logger(__name__)


class Generator:
    """Generates scene recipes based on configuration.

    This class handles the procedural generation of scene definitions (recipes)
    that are later executed by the Blender backend. It ensures logical
    reproducibility by isolating RNG states for different scene components.
    """

    def __init__(self, config: dict[str, Any] | GenConfig, output_dir: Path):
        """Initializes the generator with a configuration and output directory.

        Args:
            config: Either a dictionary or a GenConfig object.
            output_dir: Path where recipes and generated data will be stored.
        """
        if isinstance(config, dict):
            # Try to validate/convert to GenConfig
            self.config = GenConfig.model_validate(config)
        else:
            self.config = config

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.asset_provider = AssetProvider()

        # Cache textures
        self.textures = []
        if self.config.scene.texture_dir and self.config.scene.texture_dir.exists():
            valid_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            self.textures = [
                p for p in self.config.scene.texture_dir.iterdir() if p.suffix.lower() in valid_exts
            ]

    def _seed_everything(self, seed: int):
        random.seed(seed)
        np.random.seed(seed)

    def generate_all(self, exclude_ids: set[int] | None = None) -> list[SceneRecipe]:
        """Generate all scene recipes requested in the config.

        Args:
            exclude_ids: Optional set of scene IDs to skip (e.g., if already completed).

        Returns:
            List of generated SceneRecipe objects.
        """
        num_scenes = self.config.dataset.num_scenes
        exclude_ids = exclude_ids or set()
        recipes = []
        for i in range(num_scenes):
            if i in exclude_ids:
                continue
            recipes.append(self.generate_scene(i))
        return recipes

    def generate_shards(
        self,
        total_scenes: int,
        shard_index: int,
        total_shards: int,
        exclude_ids: set[int] | None = None,
    ) -> list[SceneRecipe]:
        """Generate a deterministic slice of the dataset.

        Args:
            total_scenes: Total number of scenes in the full dataset.
            shard_index: 0-based index of the current shard.
            total_shards: Total number of shards being generated.
            exclude_ids: Optional set of scene IDs to skip.

        Returns:
            List of SceneRecipe objects for the requested shard.
        """
        exclude_ids = exclude_ids or set()
        if total_shards > total_scenes:
            total_shards = total_scenes
            if shard_index >= total_shards:
                return []

        scenes_per_shard = total_scenes // total_shards
        start_idx = shard_index * scenes_per_shard

        # Ensure the last shard picks up any remainder
        end_idx = total_scenes if shard_index == total_shards - 1 else start_idx + scenes_per_shard

        logger.info(
            f"Generating Shard {shard_index + 1}/{total_shards} (Scenes {start_idx}-{end_idx})"
        )

        recipes = []
        for i in range(start_idx, end_idx):
            if i in exclude_ids:
                continue
            recipes.append(self.generate_scene(i))

        return recipes

    def generate_scene(self, scene_id: int) -> SceneRecipe:
        """Generate a single scene recipe.

        This method manages the orchestration of lighting, layout, and camera
        generation, ensuring each component uses its own isolated RNG state
        derived from the scene ID and component-specific seeds.

        Args:
            scene_id: Unique ID for the scene being generated.

        Returns:
            A complete SceneRecipe object.
        """
        recipe = SceneRecipe(scene_id=scene_id)

        # 1. Setup World/Environment (Lighting)
        # Use lighting seed to create isolated RNG
        seed_lighting = SeedManager(self.config.dataset.seeds.lighting_seed).get_shard_seed(
            scene_id
        )
        rng_lighting = random.Random(seed_lighting)
        np_rng_lighting = np.random.default_rng(seed_lighting)
        recipe.world = self._generate_world_config(rng_lighting, np_rng_lighting)

        # 2. Setup Tags and Layout
        # Use layout seed to create isolated RNG
        seed_layout = SeedManager(self.config.dataset.seeds.layout_seed).get_shard_seed(scene_id)
        rng_layout = random.Random(seed_layout)
        np_rng_layout = np.random.default_rng(seed_layout)
        recipe.objects = self._generate_layout_objects(scene_id, rng_layout, np_rng_layout)

        # 3. Setup Cameras
        # Use camera seed to create isolated RNG
        seed_camera = SeedManager(self.config.dataset.seeds.camera_seed).get_shard_seed(scene_id)
        rng_camera = random.Random(seed_camera)
        np_rng_camera = np.random.default_rng(seed_camera)
        recipe.cameras = self._generate_camera_recipes(scene_id, rng_camera, np_rng_camera)

        return recipe

    def _generate_world_config(
        self, rng: random.Random, np_rng: np.random.Generator
    ) -> WorldRecipe:
        """Generates random world environment parameters.

        Args:
            rng: Isolated Python random generator.
            np_rng: Isolated NumPy random generator.

        Returns:
            A WorldRecipe containing lighting and background configuration.
        """
        scene_config = self.config.scene
        lighting_config = scene_config.lighting

        # Resolved Texture Parameters
        texture_path = None
        texture_scale = 1.0
        texture_rotation = 0.0

        if self.textures:
            raw_texture_path = str(rng.choice(self.textures))
            texture_path = str(self.asset_provider.resolve_path(raw_texture_path))
            texture_scale = rng.uniform(
                scene_config.texture_scale_min, scene_config.texture_scale_max
            )
            if scene_config.random_texture_rotation:
                texture_rotation = rng.uniform(0, 2 * np.pi)

        background_hdri = None
        if scene_config.background_hdri:
            background_hdri = str(self.asset_provider.resolve_path(str(scene_config.background_hdri)))

        return WorldRecipe(
            background_hdri=background_hdri,
            lighting=LightingConfig(
                intensity=rng.uniform(lighting_config.intensity_min, lighting_config.intensity_max),
                radius=rng.uniform(lighting_config.radius_min, lighting_config.radius_max),
            ),
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )

    def _generate_layout_objects(
        self, scene_id: int, rng: random.Random, np_rng: np.random.Generator
    ) -> list[ObjectRecipe]:
        """Generates and places tag objects within the scene.

        Args:
            scene_id: ID of the current scene.
            rng: Isolated Python random generator.
            np_rng: Isolated NumPy random generator.

        Returns:
            List of ObjectRecipe objects representing tags and background boards.
        """
        tag_config = self.config.tag
        scenario_config = self.config.scenario
        # scene_config = self.config.scene # Not used for layout list?

        is_flying = scenario_config.flying

        # Determine layout mode
        # If layouts list is defined, iterate through it
        if scenario_config.layouts:
            layout_mode = scenario_config.layouts[scene_id % len(scenario_config.layouts)]
        else:
            layout_mode = scenario_config.layout

        objects = []

        # Calculate grid size
        grid_size = scenario_config.grid_size
        cols, rows = grid_size[0], grid_size[1]

        tag_size = tag_config.size_meters
        tag_families = [f.value for f in scenario_config.tag_families]

        # Logic for tag count
        if layout_mode == "cb":
            num_tags = (cols * rows + 1) // 2
        elif layout_mode == "aprilgrid":
            num_tags = cols * rows
        else:
            tags_range = scenario_config.tags_per_scene
            num_tags = rng.randint(tags_range[0], tags_range[1])

        # Generate Tag Objects
        for i in range(num_tags):
            family = rng.choice(tag_families)
            texture_base_path = None
            if tag_config.texture_path:
                texture_base_path = str(self.asset_provider.resolve_path(str(tag_config.texture_path)))

            tag_obj = ObjectRecipe(
                type="TAG",
                name=f"Tag_{i}",
                location=[0, 0, 0],
                rotation_euler=[0, 0, 0],
                scale=[1, 1, 1],
                properties={
                    "tag_id": i,
                    "tag_family": family,
                    "tag_size": tag_size,
                    "texture_base_path": texture_base_path,
                },
            )
            objects.append(tag_obj)

        # Apply Layout (Math only)
        if is_flying:
            apply_flying_layout(objects, self.config.physics.scatter_radius, rng=rng)
        else:
            # Layout math...
            apply_grid_layout(
                objects,
                layout_mode,
                cols,
                rows,
                tag_size,
                tag_spacing_bits=scenario_config.tag_spacing_bits or 2.0,
                tag_families=tag_families,
            )

            # Add static objects like board
            if layout_mode in ("cb", "aprilgrid", "plain"):
                # Use square_size logic consistent with geometry.layouts
                primary_family = tag_families[0]
                tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)

                tag_spacing_bits = scenario_config.tag_spacing_bits or 2
                tag_spacing = (tag_spacing_bits / tag_bit_grid_size) * tag_size
                square_size = tag_size + tag_spacing

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

        return objects

    def _generate_camera_recipes(
        self, scene_id: int, rng: random.Random, np_rng: np.random.Generator
    ) -> list[CameraRecipe]:
        """Generates multiple camera poses and sensor configurations for the scene.

        Args:
            scene_id: ID of the current scene (used for linear sweeps).
            rng: Isolated Python random generator.
            np_rng: Isolated NumPy random generator.

        Returns:
            List of CameraRecipe objects.
        """
        camera_config = self.config.camera
        scenario_config = self.config.scenario
        samples_per_scene = camera_config.samples_per_scene
        num_scenes = self.config.dataset.num_scenes

        recipes = []
        for _ in range(samples_per_scene):
            # Deterministic linear sweeps if sampling mode is set
            dist_override = None
            elev_override = None
            
            if num_scenes > 1:
                # Interpolation factor [0, 1]
                t = scene_id / (num_scenes - 1)
                
                if scenario_config.sampling_mode == "distance":
                    dist_override = camera_config.min_distance + t * (camera_config.max_distance - camera_config.min_distance)
                elif scenario_config.sampling_mode == "angle":
                    elev_override = camera_config.min_elevation + t * (camera_config.max_elevation - camera_config.min_elevation)

            pose = sample_camera_pose(
                look_at_point=[0, 0, 0],
                min_distance=camera_config.min_distance,
                max_distance=camera_config.max_distance,
                min_elevation=camera_config.min_elevation,
                max_elevation=camera_config.max_elevation,
                azimuth=camera_config.azimuth,
                distance=dist_override, # If None, sample_camera_pose uses min/max
                elevation=elev_override if elev_override is not None else camera_config.elevation,
                rng=np_rng,
            )

            # Sample velocity if configured
            velocity = None
            if camera_config.velocity_mean > 0 or camera_config.velocity_std > 0:
                # Random direction
                direction = np_rng.normal(size=3)
                norm = np.linalg.norm(direction)
                if norm > 1e-6:
                    direction /= norm
                else:
                    direction = np.array([0.0, 0.0, 1.0])

                # Random magnitude
                magnitude = np_rng.normal(camera_config.velocity_mean, camera_config.velocity_std)
                magnitude = max(0.0, magnitude)  # Assume non-negative speed
                velocity = (direction * magnitude).tolist()

            # Create Sensor Dynamics Recipe
            dynamics = SensorDynamicsRecipe(
                velocity=velocity,
                shutter_time_ms=camera_config.sensor_dynamics.shutter_time_ms,
                rolling_shutter_duration_ms=camera_config.sensor_dynamics.rolling_shutter_duration_ms,
            )

            recipes.append(
                CameraRecipe(
                    transform_matrix=pose.transform_matrix.tolist(),
                    intrinsics=self._get_intrinsics_config(),
                    sensor_dynamics=dynamics,
                    fstop=camera_config.fstop,
                    focus_distance=camera_config.focus_distance,
                    iso_noise=camera_config.iso_noise,
                    sensor_noise=camera_config.sensor_noise,
                )
            )
        return recipes

    def _get_intrinsics_config(self) -> CameraIntrinsics:
        """Helper to package camera intrinsics from config.

        Returns:
            CameraIntrinsics object.
        """
        camera_config = self.config.camera
        return CameraIntrinsics(
            resolution=list(camera_config.resolution),
            fov=camera_config.fov,
            intrinsics=camera_config.intrinsics.model_dump(),
        )

    def save_recipe_json(self, recipes: list[SceneRecipe], filename: str = "scene_recipes.json"):
        """Saves a list of scene recipes to a JSON file.

        Args:
            recipes: List of SceneRecipe objects to serialize.
            filename: Name of the output file.

        Returns:
            Path to the saved JSON file.
        """
        path = self.output_dir / filename
        # Pydantic V2: mode="json" produces a JSON-compatible dict directly
        data = [r.model_dump(mode="json") for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def _serialize_recipe(self, recipe: SceneRecipe) -> dict[str, Any]:
        return recipe.model_dump()
