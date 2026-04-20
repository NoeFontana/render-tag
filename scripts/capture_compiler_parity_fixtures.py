"""
Regenerate pinned SceneCompiler parity fixtures.

These fixtures anchor tests/unit/heavy_logic/generation/test_compiler_parity.py.
They were originally captured from the pre-consolidation Generator.generate_scene
to prove that SceneCompiler.compile_scene(validate=True) is byte-identical.

Run this script only when an intentional change to compilation behavior lands —
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
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

# Blender mocks must be injected before any render_tag import that transitively
# pulls bpy / blenderproc. The test conftest does this; reuse its helper.
from conftest import _inject_blender_mocks  # noqa: E402  # type: ignore[import-not-found]

_inject_blender_mocks()

from render_tag.core.config import GenConfig  # noqa: E402
from render_tag.generation.compiler import SceneCompiler  # noqa: E402

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "compiler_parity"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# Pinned matrix: 4 seeds x 5 scene_ids = 20 combos. Dataset size of 50 gives
# sweep mode (if ever enabled) a non-degenerate denominator and keeps scene_id
# up to 49 valid. Seeds chosen to span small/medium/large values.
SEEDS = [42, 1337, 7, 98765]
SCENE_IDS = [0, 1, 5, 10, 25]


def _make_config() -> GenConfig:
    cfg = GenConfig()
    cfg.dataset.num_scenes = 50
    # Keep the config minimal: no external textures, no HDRI, pinhole camera.
    cfg.scene.texture_dir = None
    cfg.scene.background_hdri = None
    return cfg


def _normalize(data: dict, output_dir: Path) -> dict:
    prefix = str(output_dir.absolute())
    blob = json.dumps(data)
    blob = blob.replace(prefix, "__OUTPUT_DIR__")
    return json.loads(blob)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        for seed in SEEDS:
            cfg = _make_config()
            compiler = SceneCompiler(cfg, global_seed=seed, output_dir=output_dir)
            for scene_id in SCENE_IDS:
                recipe = compiler.compile_scene(scene_id, validate=True)
                data = recipe.model_dump(mode="json")
                data = _normalize(data, output_dir)
                dst = FIXTURES_DIR / f"seed_{seed}_scene_{scene_id}.json"
                dst.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                print(f"wrote {dst.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
