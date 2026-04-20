"""
Regenerate pinned SceneCompiler parity fixtures.

These fixtures anchor tests/unit/heavy_logic/generation/test_compiler_parity.py.
They were originally captured from the pre-consolidation Generator.generate_scene
to prove that SceneCompiler.compile_scene(validate=True) is byte-identical.

Run this script only when an intentional change to compilation behavior lands -
it will overwrite every fixture with the current compiler output.

Absolute paths that embed the tmp output_dir are replaced with the placeholder
"__OUTPUT_DIR__" so fixtures are portable across machines.

    uv run python scripts/capture_compiler_parity_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

# Blender mocks must be injected before any render_tag import that transitively
# pulls bpy / blenderproc. The test conftest does this; reuse its helper.
from tests.conftest import _inject_blender_mocks  # noqa: E402

_inject_blender_mocks()

from render_tag.generation.compiler import SceneCompiler  # noqa: E402
from tests.fixtures.compiler_parity import (  # noqa: E402
    SCENE_IDS,
    SEEDS,
    fixture_path,
    make_parity_config,
    normalize_recipe_paths,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        for seed in SEEDS:
            compiler = SceneCompiler(make_parity_config(), global_seed=seed, output_dir=output_dir)
            for scene_id in SCENE_IDS:
                recipe = compiler.compile_scene(scene_id, validate=True)
                data = normalize_recipe_paths(recipe.model_dump(mode="json"), output_dir)
                dst = fixture_path(seed, scene_id)
                dst.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                print(f"wrote {dst.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
