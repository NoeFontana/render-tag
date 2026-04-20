"""Byte-parity check between SceneCompiler(validate=True) and pinned fixtures.

Fixtures under tests/fixtures/compiler_parity/ were captured from the
pre-consolidation Generator.generate_scene for a fixed (seed, scene_id)
matrix. They exist to prove that SceneCompiler.compile_scene(validate=True)
is a byte-for-byte replacement: same retry-seed derivation, same warning
filter, same resulting recipe JSON.

Regenerate via ``uv run python scripts/capture_compiler_parity_fixtures.py``
(only valid when a Generator-equivalent pre-change implementation exists).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from render_tag.generation.compiler import SceneCompiler
from tests.fixtures.compiler_parity import (
    SCENE_IDS,
    SEEDS,
    fixture_path,
    make_parity_config,
    normalize_recipe_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("scene_id", SCENE_IDS)
def test_compile_scene_validate_matches_fixture(seed: int, scene_id: int, tmp_path: Path) -> None:
    fx = fixture_path(seed, scene_id)
    expected = json.loads(fx.read_text())

    compiler = SceneCompiler(make_parity_config(), global_seed=seed, output_dir=tmp_path)
    recipe = compiler.compile_scene(scene_id, validate=True)
    actual = normalize_recipe_paths(recipe.model_dump(mode="json"), tmp_path)

    assert actual == expected, (
        f"Parity drift for seed={seed}, scene_id={scene_id}. "
        f"SceneCompiler.compile_scene(validate=True) no longer matches the pinned "
        f"fixture at {fx.relative_to(REPO_ROOT)}."
    )
