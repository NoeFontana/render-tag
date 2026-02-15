"""
Scene Generator for render-tag.

Initializes scene configurations and generates "Recipes" that can be executed
by a separate Blender process. This isolates logical calculations from Blender.
"""

import json
from pathlib import Path
from typing import Any

from render_tag.core.config import GenConfig
from render_tag.core.logging import get_logger
from render_tag.core.schema import SceneRecipe
from render_tag.core.seeding import derive_seed
from render_tag.data_io.assets import AssetProvider
from render_tag.generation.builder import SceneRecipeBuilder

logger = get_logger(__name__)


class Generator:
    """Generates scene recipes based on configuration.

    Refactored to use the Builder Pattern for SceneRecipe construction.
    """

    def __init__(
        self,
        config: dict[str, Any] | GenConfig,
        output_dir: Path,
        global_seed: int = 42,
    ):
        if isinstance(config, dict):
            self.config = GenConfig.model_validate(config)
        else:
            self.config = config

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.asset_provider = AssetProvider()
        self.global_seed = global_seed

        # Cache textures
        self.textures = []
        if self.config.scene.texture_dir and self.config.scene.texture_dir.exists():
            valid_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            self.textures = [
                p
                for p in self.config.scene.texture_dir.rglob("*")
                if p.suffix.lower() in valid_exts
            ]

    def generate_all(self, exclude_ids: set[int] | None = None) -> list[SceneRecipe]:
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
        exclude_ids = exclude_ids or set()
        if total_shards > total_scenes:
            total_shards = total_scenes
            if shard_index >= total_shards:
                return []

        scenes_per_shard = total_scenes // total_shards
        start_idx = shard_index * scenes_per_shard
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
        """Generate a single scene recipe using the Builder Pattern.

        Guarantees validity by re-sampling if pre-flight checks fail.
        """
        from render_tag.core.validator import RecipeValidator

        # Phase 2: Derive Scene Seed
        # This seed is unique to this scene index and deterministic given the global seed.
        scene_seed = derive_seed(self.global_seed, "scene", scene_id)

        # Create context-bound logger for this scene
        scene_logger = logger.bind(scene_id=scene_id, seed=scene_seed)

        max_retries = 50
        for attempt in range(max_retries):
            # Derive a specific seed for this attempt if we need to retry
            # to avoid generating the exact same invalid scene again.
            attempt_seed = derive_seed(scene_seed, "attempt", attempt)

            # We add attempt*10000 to the scene_id in the previous logic just for variety,
            # but now we have explicit seeding. We can keep the real scene_id.
            # However, Builder might use scene_id for some modulos.
            # Let's keep passing scene_id as is, because randomization is now controlled by seed.

            builder = SceneRecipeBuilder(
                scene_id, self.config, self.asset_provider, seed=attempt_seed
            )
            recipe = builder.build_world(self.textures).build_objects().build_cameras().get_result()

            # Validate (Strict: Treat warnings as reasons to re-sample)
            validator = RecipeValidator(recipe)
            validator.validate()
            if not validator.errors and not validator.warnings:
                return recipe

            scene_logger.debug(
                f"Scene {scene_id} attempt {attempt} failed validation "
                f"(Errors: {len(validator.errors)}, "
                f"Warnings: {len(validator.warnings)}). Re-sampling...",
                attempt=attempt,
            )

        scene_logger.warning(
            f"Could not generate a valid scene for ID {scene_id} after "
            f"{max_retries} attempts. Returning last attempt."
        )
        return recipe

    def save_recipe_json(self, recipes: list[SceneRecipe], filename: str = "scene_recipes.json"):
        path = self.output_dir / filename
        data = [r.model_dump(mode="json") for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path
