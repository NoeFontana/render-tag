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
    from render_tag.core.schema.subject import TagSubjectConfig
    from render_tag.generation.context import GenerationContext


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

        # Resolve number of tags (allow range sampling)
        num_tags_raw = self.config.tags_per_scene
        if isinstance(num_tags_raw, (list, tuple)):
            num_tags = int(rng.integers(num_tags_raw[0], num_tags_raw[1] + 1))
        else:
            num_tags = num_tags_raw

        tag_size_mm = self.config.size_mm
        tag_size = tag_size_mm / 1000.0  # Convert to meters for renderer
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
                tex_base = str(asset_provider.resolve_path(str(tag_config.texture_path)).absolute())

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
            # The renderer uses a 2x2 plane (from -1 to 1) and scales it by size/2.
            # To avoid double-scaling, we provide keypoints in the normalized [-1, 1] space.
            grid_size = TAG_GRID_SIZES.get(family, 8)
            margin_bits = tag_config.margin_bits
            total_bits = grid_size + (2 * margin_bits)

            # Local scale factor for the black border relative to the full plane (2x2)
            m = grid_size / total_bits
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
                tag_spacing_bits=self.config.tag_spacing_bits,
                tag_families=tag_families,
            )

            # Optional board background for better visual contrast
            if scenario.use_board:
                primary_family = tag_families[0]
                tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)
                spacing_bits = self.config.tag_spacing_bits
                tag_spacing = (spacing_bits / tag_bit_grid_size) * tag_size
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

            # Staff Engineer: Apply random offset to the group to avoid centering bias.
            # Skip this for sweep modes to maintain the geometric contract (distance/angle)
            if scenario.sampling_mode == "random":
                offset_radius = gen_config.physics.scatter_radius * 0.5
                group_offset = [
                    rng.uniform(-offset_radius, offset_radius),
                    rng.uniform(-offset_radius, offset_radius),
                    0.0,
                ]
                for obj in objects:
                    obj.location = [
                        obj.location[0] + group_offset[0],
                        obj.location[1] + group_offset[1],
                        obj.location[2] + group_offset[2],
                    ]

        return objects
