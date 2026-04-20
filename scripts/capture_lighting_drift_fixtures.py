"""Regenerate pinned SceneRecipe fixtures for the lighting-realism drift gate.

Parallels ``scripts/capture_sensor_drift_fixtures.py``. Run whenever an
intentional change to lighting benchmarks, directional presets, or the
directional-light compiler path lands — it overwrites every fixture in-place
from the current compiler output.

Absolute paths in the recipe are normalized to ``__OUTPUT_DIR__`` so
fixtures are portable across machines.

    uv run python scripts/capture_lighting_drift_fixtures.py
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
from tests.fixtures.compiler_parity import normalize_recipe_paths  # noqa: E402
from tests.fixtures.lighting_drift import (  # noqa: E402
    BENCHMARK_CONFIGS,
    CANONICAL_SCENE_IDS,
    CANONICAL_SEED,
    fixture_path,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        for name, config_path in BENCHMARK_CONFIGS:
            cfg = load_config(config_path)
            # Match the drift test: pin texture_dir to None so fixtures don't
            # depend on which PNGs happen to live on the capturing machine.
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
