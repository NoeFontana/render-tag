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

from render_tag.core.config import GenConfig
from render_tag.generation.compiler import SceneCompiler

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "compiler_parity"

SEEDS = [42, 1337, 7, 98765]
SCENE_IDS = [0, 1, 5, 10, 25]


def _make_config() -> GenConfig:
    cfg = GenConfig()
    cfg.dataset.num_scenes = 50
    cfg.scene.texture_dir = None
    cfg.scene.background_hdri = None
    return cfg


def _normalize(data: dict, output_dir: Path) -> dict:
    prefix = str(output_dir.absolute())
    blob = json.dumps(data)
    blob = blob.replace(prefix, "__OUTPUT_DIR__")
    return json.loads(blob)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("scene_id", SCENE_IDS)
def test_compile_scene_validate_matches_fixture(seed: int, scene_id: int, tmp_path: Path) -> None:
    fixture_path = FIXTURES_DIR / f"seed_{seed}_scene_{scene_id}.json"
    expected = json.loads(fixture_path.read_text())

    compiler = SceneCompiler(_make_config(), global_seed=seed, output_dir=tmp_path)
    recipe = compiler.compile_scene(scene_id, validate=True)
    actual = _normalize(recipe.model_dump(mode="json"), tmp_path)

    assert actual == expected, (
        f"Parity drift for seed={seed}, scene_id={scene_id}. "
        f"SceneCompiler.compile_scene(validate=True) no longer matches the pinned "
        f"fixture at {fixture_path.name}."
    )
