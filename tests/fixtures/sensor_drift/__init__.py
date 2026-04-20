"""Pinned SceneRecipe fixtures for the sensor-realism drift gate.

Fixtures are compiled-recipe snapshots for each sensor benchmark. The drift
test compares live-compiled recipes to these snapshots; any intentional
pixel-intent change requires re-running
``scripts/capture_sensor_drift_fixtures.py`` in the same PR.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

BENCHMARK_CONFIGS: tuple[tuple[str, str], ...] = (
    ("locus_v1_high_iso", "configs/benchmarks/sensor/locus_v1_high_iso.yaml"),
    ("locus_v1_low_dr_outdoor", "configs/benchmarks/sensor/locus_v1_low_dr_outdoor.yaml"),
    ("locus_v1_raw_pipeline", "configs/benchmarks/sensor/locus_v1_raw_pipeline.yaml"),
)

CANONICAL_SEED = 42
CANONICAL_SCENE_IDS: tuple[int, ...] = (0, 1, 5)


def fixture_path(benchmark_name: str, scene_id: int) -> Path:
    return FIXTURES_DIR / f"{benchmark_name}_scene_{scene_id}.json"
