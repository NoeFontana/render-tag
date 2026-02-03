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
from render_tag.config import GenConfig
from render_tag.geometry.camera import sample_camera_pose
from render_tag.geometry.layouts import apply_flying_layout, apply_grid_layout
from render_tag.schema import (
    CameraIntrinsics,
    CameraRecipe,
    LightingConfig,
    ObjectRecipe,
    SceneRecipe,
    WorldRecipe,
)

# Removed dataclasses as they are replaced by schema.py imports


class Generator:
    """Generates scene recipes based on configuration."""

    def __init__(self, config: dict[str, Any] | GenConfig, output_dir: Path):
        if isinstance(config, dict):
            # Try to validate/convert to GenConfig
            self.config = GenConfig.model_validate(config)
        else:
            self.config = config

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _seed_everything(self, seed: int):
        random.seed(seed)
        np.random.seed(seed)

    def generate_all(self) -> list[SceneRecipe]:
        """Generate all scene recipes requested in the config."""
        num_scenes = self.config.dataset.num_scenes
        recipes = []
        for i in range(num_scenes):
            recipes.append(self.generate_scene(i))
        return recipes

    def generate_shards(
        self, total_scenes: int, shard_index: int, total_shards: int
    ) -> list[SceneRecipe]:
        """Generate a deterministic slice of the dataset."""
        if total_shards > total_scenes:
            total_shards = total_scenes
            if shard_index >= total_shards:
                return []

        scenes_per_shard = total_scenes // total_shards
        start_idx = shard_index * scenes_per_shard

        # Ensure the last shard picks up any remainder
        end_idx = total_scenes if shard_index == total_shards - 1 else start_idx + scenes_per_shard

        print(f"Generating Shard {shard_index + 1}/{total_shards} (Scenes {start_idx}-{end_idx})")

        recipes = []
        for i in range(start_idx, end_idx):
            recipes.append(self.generate_scene(i))

        return recipes

    def generate_scene(self, scene_id: int) -> SceneRecipe:
        """Generate a single scene recipe."""
        recipe = SceneRecipe(scene_id=scene_id)

        # 1. Setup World/Environment (Lighting)
        # Use lighting seed
        self._seed_everything(self.config.dataset.seeds.lighting_seed + scene_id)
        recipe.world = self._generate_world_config()

        # 2. Setup Tags and Layout
        # Use layout seed
        self._seed_everything(self.config.dataset.seeds.layout_seed + scene_id)
        recipe.objects = self._generate_layout_objects(scene_id)

        # 3. Setup Cameras
        # Use camera seed
        self._seed_everything(self.config.dataset.seeds.camera_seed + scene_id)
        recipe.cameras = self._generate_camera_recipes()

        return recipe

    def _generate_world_config(self) -> WorldRecipe:
        scene_config = self.config.scene
        lighting_config = scene_config.lighting

        # Resolved Texture Parameters
        texture_path = None
        texture_scale = 1.0
        texture_rotation = 0.0

        if scene_config.texture_dir and scene_config.texture_dir.exists():
            # Filter for valid image extensions
            valid_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            textures = [
                p for p in scene_config.texture_dir.iterdir() if p.suffix.lower() in valid_exts
            ]
            if textures:
                texture_path = str(random.choice(textures))
                texture_scale = random.uniform(
                    scene_config.texture_scale_min, scene_config.texture_scale_max
                )
                if scene_config.random_texture_rotation:
                    texture_rotation = random.uniform(0, 2 * np.pi)

        return WorldRecipe(
            background_hdri=str(scene_config.background_hdri)
            if scene_config.background_hdri
            else None,
            lighting=LightingConfig(
                intensity=random.uniform(
                    lighting_config.intensity_min, lighting_config.intensity_max
                ),
                radius=random.uniform(lighting_config.radius_min, lighting_config.radius_max),
            ),
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )

    def _generate_layout_objects(self, scene_id: int) -> list[ObjectRecipe]:
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

        # Check if single tag family forced in config (backwards compat?)
        # tag_config.family is an enum
        # But scenario typically overrides

        # Logic for tag count
        if layout_mode == "cb":
            num_tags = (cols * rows + 1) // 2
        elif layout_mode == "aprilgrid":
            num_tags = cols * rows
        else:
            tags_range = scenario_config.tags_per_scene
            num_tags = random.randint(tags_range[0], tags_range[1])

        # Generate Tag Objects
        for i in range(num_tags):
            family = random.choice(tag_families)
            texture_base_path = str(tag_config.texture_path) if tag_config.texture_path else None

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
            apply_flying_layout(objects, self.config.physics.scatter_radius)
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

    def _generate_camera_recipes(self) -> list[CameraRecipe]:
        camera_config = self.config.camera
        samples_per_scene = camera_config.samples_per_scene

        recipes = []
        for _ in range(samples_per_scene):
            # Sample pose
            pose = sample_camera_pose(
                look_at_point=[0, 0, 0],
                min_distance=camera_config.min_distance,
                max_distance=camera_config.max_distance,
                min_elevation=camera_config.min_elevation,
                max_elevation=camera_config.max_elevation,
                azimuth=camera_config.azimuth,
                elevation=camera_config.elevation,
            )

            # Sample velocity if configured
            velocity = None
            if camera_config.velocity_mean > 0 or camera_config.velocity_std > 0:
                # Random direction
                direction = np.random.normal(size=3)
                norm = np.linalg.norm(direction)
                if norm > 1e-6:
                    direction /= norm
                else:
                    direction = np.array([0.0, 0.0, 1.0])

                # Random magnitude
                magnitude = np.random.normal(
                    camera_config.velocity_mean, camera_config.velocity_std
                )
                magnitude = max(0.0, magnitude)  # Assume non-negative speed
                velocity = (direction * magnitude).tolist()

            recipes.append(
                CameraRecipe(
                    transform_matrix=pose.transform_matrix.tolist(),
                    intrinsics=self._get_intrinsics_config(),
                    velocity=velocity,
                    shutter_time_ms=camera_config.shutter_time_ms,
                    fstop=camera_config.fstop,
                    focus_distance=camera_config.focus_distance,
                    iso_noise=camera_config.iso_noise,
                )
            )
        return recipes

    def _get_intrinsics_config(self) -> CameraIntrinsics:
        camera_config = self.config.camera
        return CameraIntrinsics(
            resolution=list(camera_config.resolution),
            fov=camera_config.fov,
            intrinsics=camera_config.intrinsics.model_dump(),
        )

    def save_recipe_json(self, recipes: list[SceneRecipe], filename: str = "scene_recipes.json"):
        path = self.output_dir / filename
        # Pydantic serialization
        data = [json.loads(r.model_dump_json()) for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def _serialize_recipe(self, recipe: SceneRecipe) -> dict[str, Any]:
        return recipe.model_dump()
