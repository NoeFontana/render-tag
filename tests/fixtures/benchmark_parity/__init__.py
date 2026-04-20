"""Pinned SceneRecipe fixtures for the full benchmark-parity drift gate.

Where ``sensor_drift`` and ``lighting_drift`` each cover one sub-tree of the
compiled recipe, this fixture set snapshots the *entire* recipe for every
benchmark in ``configs/benchmarks/``. It is the v1.0 regression baseline:
preset composition, tag material bounds, ppm_constraint, scenario subject,
and scene texture setup must all stay bit-identical against intentional
updates (which re-run the regeneration script in the same PR).

Fixtures are tracked per benchmark family (``locus_v1_*.json``,
``calibration_*.json``) so new families can be added without disturbing
existing entries.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

LOCUS_V1_BENCHMARKS: tuple[tuple[str, str], ...] = (
    ("locus_v1_tag36h11", "configs/benchmarks/single_tag/locus_v1_tag36h11.yaml"),
    ("locus_v1_tag16h5", "configs/benchmarks/single_tag/locus_v1_tag16h5.yaml"),
    ("locus_v1_high_iso", "configs/benchmarks/sensor/locus_v1_high_iso.yaml"),
    ("locus_v1_low_dr_outdoor", "configs/benchmarks/sensor/locus_v1_low_dr_outdoor.yaml"),
    ("locus_v1_raw_pipeline", "configs/benchmarks/sensor/locus_v1_raw_pipeline.yaml"),
    ("locus_v1_low_key", "configs/benchmarks/lighting/locus_v1_low_key.yaml"),
    ("locus_v1_hard_shadows", "configs/benchmarks/lighting/locus_v1_hard_shadows.yaml"),
)

CALIBRATION_BENCHMARKS: tuple[tuple[str, str], ...] = (
    (
        "calibration_aprilgrid_golden_v1",
        "configs/benchmarks/calibration/aprilgrid_golden_v1.yaml",
    ),
    (
        "calibration_aprilgrid_kalibr",
        "configs/benchmarks/calibration/aprilgrid_kalibr.yaml",
    ),
    (
        "calibration_aprilgrid_distortion_brown_conrady_v1",
        "configs/benchmarks/calibration/aprilgrid_distortion_brown_conrady_v1.yaml",
    ),
    (
        "calibration_aprilgrid_distortion_kannala_brandt_v1",
        "configs/benchmarks/calibration/aprilgrid_distortion_kannala_brandt_v1.yaml",
    ),
    (
        "calibration_charuco_golden_v1",
        "configs/benchmarks/calibration/charuco_golden_v1.yaml",
    ),
    (
        "calibration_charuco_baseline",
        "configs/benchmarks/calibration/charuco_baseline.yaml",
    ),
    (
        "calibration_charuco_opencv",
        "configs/benchmarks/calibration/charuco_opencv.yaml",
    ),
)

BENCHMARK_CONFIGS: tuple[tuple[str, str], ...] = LOCUS_V1_BENCHMARKS + CALIBRATION_BENCHMARKS

CANONICAL_SEED = 42
CANONICAL_SCENE_IDS: tuple[int, ...] = (0, 1, 5)


def fixture_path(benchmark_name: str, scene_id: int) -> Path:
    return FIXTURES_DIR / f"{benchmark_name}_scene_{scene_id}.json"
