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

from render_tag.common.logging import get_logger
from render_tag.core.config import GenConfig
from render_tag.data_io.assets import AssetProvider
from render_tag.generation.builder import SceneRecipeBuilder
from render_tag.schema import SceneRecipe

logger = get_logger(__name__)


class Generator:
    """Generates scene recipes based on configuration.

    Refactored to use the Builder Pattern for SceneRecipe construction.
    """

    def __init__(self, config: dict[str, Any] | GenConfig, output_dir: Path):
        if isinstance(config, dict):
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
        """Generate a single scene recipe using the Builder Pattern."""
        builder = SceneRecipeBuilder(scene_id, self.config, self.asset_provider)
        return (
            builder.build_world(self.textures)
            .build_objects()
            .build_cameras()
            .get_result()
        )

    def save_recipe_json(self, recipes: list[SceneRecipe], filename: str = "scene_recipes.json"):
        path = self.output_dir / filename
        data = [r.model_dump(mode="json") for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path
