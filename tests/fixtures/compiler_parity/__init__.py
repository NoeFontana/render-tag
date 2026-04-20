"""Shared constants and helpers for the SceneCompiler parity fixture suite.

Both the regeneration script (``scripts/capture_compiler_parity_fixtures.py``)
and the test (``tests/unit/heavy_logic/generation/test_compiler_parity.py``)
must agree on the pinned (seed, scene_id) matrix, the minimal GenConfig, and
the output-dir path normalisation — otherwise fixtures and assertions drift.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from render_tag.core.config import GenConfig

# Tolerance for float leaves in recipe comparisons. One ULP near 1.0 is
# ~1.1e-16; we accept up to ~1000 ULPs of accumulated rounding noise but nothing
# larger. Any genuine semantic drift (unit change, sign flip, seed derivation
# bug) moves values by many orders of magnitude beyond this and still fails.
FLOAT_REL_TOL = 1e-13
FLOAT_ABS_TOL = 1e-13

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


def diff_recipes(actual: Any, expected: Any, *, path: str = "$") -> list[str]:
    """Recursively compare two JSON-shaped values, tolerating float ULP noise.

    Returns a list of human-readable mismatch paths; an empty list means the
    structures match. Floats are compared with ``math.isclose`` using
    ``FLOAT_REL_TOL`` / ``FLOAT_ABS_TOL`` — tight enough that any real semantic
    drift still trips the test, but loose enough to absorb last-bit rounding
    noise that leaks in across runtimes / worker orderings.

    Non-float leaves (ints, strings, bools, None) are compared for exact
    equality. Containers must match in shape (dict keys, list length) before
    leaves are compared.
    """
    # bool is a subclass of int — handle explicitly so ``True == 1`` does not
    # silently pass.
    if isinstance(actual, bool) or isinstance(expected, bool):
        if actual is not expected:
            return [f"{path}: {actual!r} != {expected!r}"]
        return []
    if isinstance(actual, float) or isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            return [f"{path}: type mismatch ({type(actual).__name__} vs {type(expected).__name__})"]
        if math.isclose(
            float(actual), float(expected), rel_tol=FLOAT_REL_TOL, abs_tol=FLOAT_ABS_TOL
        ):
            return []
        return [f"{path}: {actual!r} != {expected!r} (beyond float tolerance)"]
    if isinstance(actual, dict) and isinstance(expected, dict):
        mismatches: list[str] = []
        extra = actual.keys() - expected.keys()
        missing = expected.keys() - actual.keys()
        for key in sorted(extra):
            mismatches.append(f"{path}.{key}: unexpected key")
        for key in sorted(missing):
            mismatches.append(f"{path}.{key}: missing key")
        for key in sorted(actual.keys() & expected.keys()):
            mismatches.extend(diff_recipes(actual[key], expected[key], path=f"{path}.{key}"))
        return mismatches
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return [f"{path}: length {len(actual)} != {len(expected)}"]
        mismatches = []
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            mismatches.extend(diff_recipes(a, e, path=f"{path}[{i}]"))
        return mismatches
    if actual != expected:
        return [f"{path}: {actual!r} != {expected!r}"]
    return []
