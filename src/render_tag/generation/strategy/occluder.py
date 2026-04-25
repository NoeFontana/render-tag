"""OccluderStrategy: shadow-casting fixtures placed along the SUN ray.

Placing an occluder at world position ``P = target + d * sun_dir`` (where
``sun_dir`` points from origin toward the SUN) guarantees the umbra of P
on the tag plane (z=0) lands at ``target_xy`` for a parallel SUN — the
azimuth/elevation cancels out under the projection. Lateral jitter then
shifts the umbra so its edge crosses the tag rather than centers on it.

This strategy is invoked separately from ``SubjectStrategy`` because
occluders coexist with the tag subject; the compiler calls both and
appends the results to ``recipe.objects``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from render_tag.core.geometry.math import sun_lateral_axis, sun_unit_vector
from render_tag.core.schema.recipe import ObjectRecipe
from render_tag.core.seeding import derive_seed

if TYPE_CHECKING:
    from render_tag.core.schema.subject import OccluderConfig
    from render_tag.generation.context import GenerationContext


class OccluderStrategy:
    """Sample occluder primitives whose umbra crosses the target position."""

    def __init__(self, config: OccluderConfig):
        self.config = config

    def prepare_assets(self, context: GenerationContext) -> None:
        pass

    def sample_pose(
        self,
        seed: int,
        context: GenerationContext,
        target_position: tuple[float, float, float],
    ) -> list[ObjectRecipe]:
        """Return occluder ObjectRecipes positioned along the SUN ray.

        Args:
            seed: Scene-specific random seed.
            context: Shared generation context (carries the resolved lighting).
            target_position: World-space (x, y, z) the umbra should cross —
                typically the centroid of tag positions after layout.
        """
        if not self.config.enabled:
            return []

        gen_config = context.gen_config
        if gen_config is None:
            raise ValueError("gen_config is required in GenerationContext")

        directional = gen_config.scene.lighting.directional
        if not directional:
            return []

        sun = directional[0]
        sun_dir = sun_unit_vector(sun.azimuth, sun.elevation)
        lateral = sun_lateral_axis(sun.azimuth)
        rot_z = sun.azimuth + math.pi / 2

        rng = np.random.default_rng(derive_seed(seed, "occluder_layout", 0))
        n = int(rng.integers(self.config.count_min, self.config.count_max + 1))

        objects: list[ObjectRecipe] = []
        tx, ty, tz = target_position

        for i in range(n):
            d = float(rng.uniform(self.config.offset_min_m, self.config.offset_max_m))
            jitter = float(
                rng.uniform(-self.config.lateral_jitter_m, self.config.lateral_jitter_m)
            )

            x = tx + d * sun_dir[0] + jitter * lateral[0]
            y = ty + d * sun_dir[1] + jitter * lateral[1]
            z = tz + d * sun_dir[2]

            objects.append(
                ObjectRecipe(
                    type="OCCLUDER",
                    name=f"Occluder_{i}",
                    location=[x, y, z],
                    rotation_euler=[0.0, 0.0, rot_z],
                    scale=[1.0, 1.0, 1.0],
                    properties={
                        "shape": self.config.shape,
                        "width_m": self.config.width_m,
                        "length_m": self.config.length_m,
                        "albedo": self.config.albedo,
                        "roughness": self.config.roughness,
                    },
                )
            )

        return objects
