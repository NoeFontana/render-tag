"""Regenerate pinned SceneRecipe fixtures for the full benchmark-parity gate.

Where ``capture_sensor_drift_fixtures.py`` and
``capture_lighting_drift_fixtures.py`` each snapshot one sub-tree of the
compiled recipe, this script snapshots the *entire* recipe for every
benchmark in ``tests/fixtures/benchmark_parity/BENCHMARK_CONFIGS``.

    uv run python scripts/capture_benchmark_parity_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from tests._plugins.blender_mocks.plugin import _inject_blender_mocks  # noqa: E402

_inject_blender_mocks()

from render_tag.core.config import load_config  # noqa: E402
from render_tag.generation.compiler import SceneCompiler  # noqa: E402
from tests.fixtures.benchmark_parity import (  # noqa: E402
    BENCHMARK_CONFIGS,
    CANONICAL_SCENE_IDS,
    CANONICAL_SEED,
    fixture_path,
)
from tests.fixtures.compiler_parity import normalize_recipe_paths  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        for name, config_path in BENCHMARK_CONFIGS:
            cfg = load_config(config_path)
            # Parity is about compiler/schema/preset semantics, not asset
            # availability. Texture pick depends on a filesystem listing that
            # CI doesn't share with dev machines; pinning to None makes
            # fixtures portable.
            cfg.scene.texture_dir = None
            compiler = SceneCompiler(cfg, global_seed=CANONICAL_SEED, output_dir=output_dir)
            for scene_id in CANONICAL_SCENE_IDS:
                recipe = compiler.compile_scene(scene_id, validate=True)
                data = normalize_recipe_paths(recipe.model_dump(mode="json"), output_dir)
                dst = fixture_path(name, scene_id)
                dst.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                print(f"wrote {dst.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
