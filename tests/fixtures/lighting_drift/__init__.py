"""Pinned SceneRecipe fixtures for the lighting-realism drift gate.

Parallels ``tests/fixtures/sensor_drift``. Each fixture is a compiled-recipe
snapshot for a lighting benchmark; the drift test compares live-compiled
recipes to these snapshots. Any intentional change to directional-light
plumbing, lighting presets, or benchmark configs requires re-running
``scripts/capture_lighting_drift_fixtures.py`` in the same PR.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

BENCHMARK_CONFIGS: tuple[tuple[str, str], ...] = (
    ("locus_v1_hard_shadows", "configs/benchmarks/lighting/locus_v1_hard_shadows.yaml"),
    ("locus_v1_low_key", "configs/benchmarks/lighting/locus_v1_low_key.yaml"),
)

CANONICAL_SEED = 42
CANONICAL_SCENE_IDS: tuple[int, ...] = (0, 1, 5)


def fixture_path(benchmark_name: str, scene_id: int) -> Path:
    return FIXTURES_DIR / f"{benchmark_name}_scene_{scene_id}.json"
