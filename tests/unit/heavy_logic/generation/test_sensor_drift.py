"""Drift gate for sensor-realism benchmarks.

Compiles each sensor benchmark config and diffs the resulting
``SceneRecipe`` against a pinned JSON fixture. Any semantic change to a
preset, schema field, or compiler path that alters pixel intent trips this
test — the correct response is to re-run
``scripts/capture_sensor_drift_fixtures.py`` and commit the updated fixtures
in the same PR.

The diff tolerates float-ULP noise (see ``diff_recipes``) so cross-runtime
last-bit differences don't false-positive; any genuine semantic drift moves
values far beyond that tolerance.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from render_tag.core.config import load_config
from render_tag.generation.compiler import SceneCompiler
from tests.fixtures.compiler_parity import diff_recipes, normalize_recipe_paths
from tests.fixtures.sensor_drift import (
    BENCHMARK_CONFIGS,
    CANONICAL_SCENE_IDS,
    CANONICAL_SEED,
    fixture_path,
)


@pytest.fixture(
    scope="module", params=BENCHMARK_CONFIGS, ids=[name for name, _ in BENCHMARK_CONFIGS]
)
def benchmark_compiler(request: pytest.FixtureRequest) -> Iterator[tuple[str, SceneCompiler, Path]]:
    name, config_path = request.param
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        cfg = load_config(config_path)
        yield (
            name,
            SceneCompiler(cfg, global_seed=CANONICAL_SEED, output_dir=output_dir),
            output_dir,
        )


@pytest.mark.parametrize("scene_id", CANONICAL_SCENE_IDS)
def test_sensor_benchmark_recipe_matches_fixture(
    benchmark_compiler: tuple[str, SceneCompiler, Path], scene_id: int
) -> None:
    name, compiler, output_dir = benchmark_compiler
    fixture = fixture_path(name, scene_id)
    if not fixture.exists():
        pytest.fail(
            f"missing fixture {fixture.name} — "
            "run `uv run python scripts/capture_sensor_drift_fixtures.py` to generate."
        )

    expected = json.loads(fixture.read_text())
    recipe = compiler.compile_scene(scene_id, validate=True)
    actual = normalize_recipe_paths(recipe.model_dump(mode="json"), output_dir)

    mismatches = diff_recipes(actual, expected)
    assert not mismatches, (
        f"SceneRecipe drift for {name} scene {scene_id}:\n  "
        + "\n  ".join(mismatches[:20])
        + (f"\n  ... and {len(mismatches) - 20} more" if len(mismatches) > 20 else "")
        + "\n\nIf this change is intentional, re-run "
        "`uv run python scripts/capture_sensor_drift_fixtures.py` "
        "and commit the updated fixtures."
    )
