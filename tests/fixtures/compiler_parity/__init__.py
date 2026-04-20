"""Shared constants and helpers for the SceneCompiler parity fixture suite.

Both the regeneration script (``scripts/capture_compiler_parity_fixtures.py``)
and the test (``tests/unit/heavy_logic/generation/test_compiler_parity.py``)
must agree on the pinned (seed, scene_id) matrix, the minimal GenConfig, and
the output-dir path normalisation — otherwise fixtures and assertions drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from render_tag.core.config import GenConfig

FIXTURES_DIR = Path(__file__).resolve().parent

# Pinned matrix: 4 seeds x 5 scene_ids = 20 combos. Dataset size of 50 gives
# sweep mode (if ever enabled) a non-degenerate denominator and keeps scene_id
# up to 49 valid. Seeds chosen to span small/medium/large values.
SEEDS: tuple[int, ...] = (42, 1337, 7, 98765)
SCENE_IDS: tuple[int, ...] = (0, 1, 5, 10, 25)
DATASET_NUM_SCENES = 50

OUTPUT_DIR_PLACEHOLDER = "__OUTPUT_DIR__"


def make_parity_config() -> GenConfig:
    """Minimal config: no external textures, no HDRI, pinhole camera."""
    cfg = GenConfig()
    cfg.dataset.num_scenes = DATASET_NUM_SCENES
    cfg.scene.texture_dir = None
    cfg.scene.background_hdri = None
    return cfg


def normalize_recipe_paths(data: dict, output_dir: Path) -> dict:
    """Replace absolute tmp paths with a placeholder so fixtures are portable."""
    prefix = str(output_dir.absolute())
    blob = json.dumps(data)
    blob = blob.replace(prefix, OUTPUT_DIR_PLACEHOLDER)
    return json.loads(blob)


def fixture_path(seed: int, scene_id: int) -> Path:
    return FIXTURES_DIR / f"seed_{seed}_scene_{scene_id}.json"
