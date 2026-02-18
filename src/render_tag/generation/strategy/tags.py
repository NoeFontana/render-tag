
"""
Tag Strategy implementation for individual marker generation.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from render_tag.core.config import TAG_MAX_IDS
from render_tag.core.constants import TAG_GRID_SIZES
from render_tag.core.schema.recipe import ObjectRecipe
from render_tag.core.seeding import derive_seed
from render_tag.data_io.assets import AssetProvider
from render_tag.generation.layouts import apply_flying_layout, apply_grid_layout

from .base import SubjectStrategy

if TYPE_CHECKING:
    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.schema.subject import TagSubjectConfig


class TagStrategy(SubjectStrategy):
    """Strategy for scattering individual fiducial markers in a scene.
    
    This strategy handles the generation of multiple independent tags, applying
    various layout algorithms (e.g., flying, grid) and resolving material
    randomization for each tag instance.
    """

    def __init__(self, config: TagSubjectConfig):
        """Initialize the strategy with specific tag configuration.
        
        Args:
            config: Configuration for the tag subject domain.
        """
        self.config = config

    def prepare_assets(self, context: GenerationContext) -> None:
        """Currently, tag textures are generated/resolved per-object if needed.
        
        Future optimization: Pre-generate all unique tags required for the
        job to minimize filesystem I/O during the sampling loop.

        Args:
            context: The shared generation context.
        """
        pass

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        """Generate a list of tags with deterministic random poses.
        
        Args:
            seed: Scene-specific random seed.
            context: Shared generation context.
            
        Returns:
            A list of ObjectRecipe instructions for the renderer.
        """
        layout_seed = derive_seed(seed, "layout", 0)
        rng = np.random.default_rng(layout_seed)
        
        gen_config = context.gen_config
        if gen_config is None:
            raise ValueError("gen_config is required in GenerationContext")
            
        tag_config = gen_config.tag
        scenario = gen_config.scenario
        
        num_tags = self.config.tags_per_scene
        tag_size = self.config.size_meters
        tag_families = self.config.tag_families
        
        objects = []
        asset_provider = AssetProvider()
        
        for i in range(num_tags):
            obj_seed = derive_seed(layout_seed, "tag_obj", i)
            obj_rng = np.random.default_rng(obj_seed)

            family = obj_rng.choice(tag_families)
            max_id = TAG_MAX_IDS.get(family, 100)
            tag_id = int(obj_rng.integers(0, max_id))

            # Resolve tag material properties (Domain Randomization)
            roughness = 0.8
            specular = 0.2
            if tag_config.material and tag_config.material.randomize:
                roughness = obj_rng.uniform(
                    tag_config.material.roughness_min, tag_config.material.roughness_max
                )
                specular = obj_rng.uniform(
                    tag_config.material.specular_min, tag_config.material.specular_max
                )

            # Resolve custom texture base path (for external assets)
            tex_base = None
            if tag_config.texture_path:
                tex_base = str(
                    asset_provider.resolve_path(str(tag_config.texture_path)).absolute()
                )

            # Resolve texture path to the local cache directory
            texture_path = None
            if context.output_dir:
                margin_bits = tag_config.margin_bits
                texture_path = str(
                    (
                        context.output_dir
                        / "cache"
                        / "tags"
                        / f"{family}_{tag_id}_m{margin_bits}.png"
                    ).absolute()
                )

            # Define 3D Keypoints in local object space (TL, TR, BR, BL order)
            m = tag_size / 2.0
            kps = [[-m, m, 0.0], [m, m, 0.0], [m, -m, 0.0], [-m, -m, 0.0]]

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
                    keypoints_3d=kps,
                )
            )

        # Apply layout algorithm based on scenario configuration
        if scenario.flying:
            apply_flying_layout(objects, gen_config.physics.scatter_radius, rng=rng)
        else:
            # Standard grid layout for non-physics simulations
            cols = math.ceil(math.sqrt(num_tags))
            rows = math.ceil(num_tags / cols)
            apply_grid_layout(
                objects,
                "plain",
                cols,
                rows,
                tag_size,
                tag_spacing_bits=2.0,
                tag_families=tag_families,
            )
            
            # Optional board background for better visual contrast
            if scenario.use_board:
                primary_family = tag_families[0]
                tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
                tag_spacing = (2.0 / tag_bit_grid_size) * tag_size
                square_size = tag_size + tag_spacing
                objects.append(
                    ObjectRecipe(
                        type="BOARD",
                        name="Board_Background",
                        location=[0, 0, -0.005],
                        rotation_euler=[0, 0, 0],
                        scale=[1, 1, 1],
                        properties={
                            "mode": "plain",
                            "cols": cols,
                            "rows": rows,
                            "tag_size": tag_size,
                            "square_size": square_size,
                        },
                    )
                )
                
        return objects
