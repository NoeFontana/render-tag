"""
Scene Generator for render-tag.

Initializes scene configurations and generates "Recipes" that can be executed
by a separate Blender process. This isolates logical calculations from Blender.
"""

import json
from pathlib import Path

import numpy as np

from ..core.config import GenConfig
from ..core.logging import get_logger
from ..core.schema import SceneRecipe
from ..core.seeding import derive_seed
from .compiler import SceneCompiler

logger = get_logger(__name__)


class Generator:
    """Generates scene recipes based on configuration.

    Refactored to use the SceneCompiler for rigid, deterministic construction.
    """

    def __init__(
        self,
        config: GenConfig,
        output_dir: Path,
        global_seed: int = 42,
    ):
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.global_seed = global_seed
        self.rng = np.random.default_rng(global_seed)
        self.compiler = SceneCompiler(config, global_seed=global_seed, output_dir=output_dir)

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
        recipes = self.compiler.compile_shards(
            shard_index=shard_index,
            total_shards=total_shards,
            exclude_ids=exclude_ids,
        )
        return recipes

    def generate_scene(self, scene_id: int) -> SceneRecipe:
        """Generate a single scene recipe using the Compiler.

        Guarantees validity by re-sampling if pre-flight checks fail.
        """
        from ..core.validator import RecipeValidator

        # Phase 2: Derive Scene Seed
        scene_seed = derive_seed(self.global_seed, "scene", scene_id)
        scene_logger = logger.bind(scene_id=scene_id, seed=scene_seed)

        max_retries = 50
        for attempt in range(max_retries):
            # Derive a specific seed for this attempt if we need to retry
            attempt_seed = derive_seed(scene_seed, "attempt", attempt)

            recipe = self.compiler._build_recipe(scene_id, attempt_seed)

            # Validate (Strict: Treat warnings as reasons to re-sample)
            validator = RecipeValidator(recipe)
            validator.validate()
            
            # Staff Engineer: Filter out cache-pending warnings during the generation phase
            # as these are expected to be resolved immediately after this call.
            relevant_warnings = [
                w for w in validator.warnings if "Cache asset not yet present" not in w
            ]
            
            if not validator.errors and not relevant_warnings:
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
