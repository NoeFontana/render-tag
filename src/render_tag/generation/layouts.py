"""
Layout algorithms for render-tag scene generation.
"""

from typing import Any

import numpy as np

from ..core.constants import TAG_GRID_SIZES
from ..core.schema import ObjectRecipe
from .board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
)


def apply_flying_layout(
    objects: list[ObjectRecipe], radius: float, rng: np.random.Generator | None = None
):
    """Apply a random 3D distribution to objects."""
    if rng is None:
        rng = np.random.default_rng()

    for obj in objects:
        obj.location = [
            rng.uniform(-radius, radius),
            rng.uniform(-radius, radius),
            rng.uniform(0.1, radius * 2),
        ]
        obj.rotation_euler = [
            rng.uniform(0, 2 * np.pi),
            rng.uniform(0, 2 * np.pi),
            rng.uniform(0, 2 * np.pi),
        ]


def apply_grid_layout(
    objects: list[ObjectRecipe],
    mode: str,
    cols: int,
    rows: int,
    tag_size: float,
    tag_spacing_bits: float = 2.0,
    tag_families: list[str] | None = None,
):
    """Apply grid layout (plain, ChArUco, AprilGrid) to objects."""
    if not tag_families:
        return

    primary_family = tag_families[0]
    tag_bit_grid_size = TAG_GRID_SIZES.get(primary_family, 8)

    tag_spacing = (tag_spacing_bits / tag_bit_grid_size) * tag_size
    square_size = tag_size + tag_spacing
    marker_margin = tag_spacing / 2.0
    corner_size = tag_spacing

    if mode == "plain":
        n = len(objects)
        if n == 0:
            return
        cell_size = tag_size + tag_spacing
        grid_cols = cols or int(np.ceil(np.sqrt(n)))
        grid_rows = rows or int(np.ceil(n / grid_cols))

        grid_width = (grid_cols - 1) * cell_size
        grid_height = (grid_rows - 1) * cell_size
        start_x = -grid_width / 2
        start_y = +grid_height / 2  # CV-Standard: Start at top

        for i, obj in enumerate(objects):
            col, row = i % grid_cols, i // grid_cols
            obj.location = [
                start_x + col * cell_size,
                start_y - row * cell_size,  # Move down for subsequent rows
                0.001,
            ]

    elif mode == "cb":
        spec = BoardSpec(
            rows=rows,
            cols=cols,
            square_size=square_size,
            marker_margin=marker_margin,
            board_type=BoardType.CHARUCO,
        )
        layout = compute_charuco_layout(spec, center=(0, 0, 0))
        _apply_layout_to_objects(objects, layout, spec.marker_size)

    elif mode == "aprilgrid":
        spec = BoardSpec(
            rows=rows,
            cols=cols,
            square_size=square_size,
            marker_margin=marker_margin,
            board_type=BoardType.APRILGRID,
        )
        layout = compute_aprilgrid_layout(spec, corner_size=corner_size, center=(0, 0, 0))
        _apply_layout_to_objects(objects, layout, spec.marker_size)


def _apply_layout_to_objects(objects: list[ObjectRecipe], layout: Any, marker_size: float):
    """Internal helper to map layout squares to object recipes."""
    tag_idx = 0
    for sq in layout.squares:
        if sq.has_tag and tag_idx < len(objects):
            obj = objects[tag_idx]
            obj.location = [sq.center.x, sq.center.y, 0.001]
            obj.properties["marker_size"] = marker_size
            tag_idx += 1
