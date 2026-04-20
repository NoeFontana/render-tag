"""Lint: every locus_v1 benchmark YAML lists ``locus.v1_baseline`` first.

Preset composition is left-to-right with later entries winning on conflicts.
``locus.v1_baseline`` bundles shared defaults (rig, tag material, ppm
constraint, default scene.lighting); scenario presets (``sensor.*``,
``lighting.*``, ``shadow.*``) are expected to compose on top and override
those defaults. Listing the baseline anywhere but first silently reverts
sensor / lighting to baseline values — hard to notice, easy to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.fixtures.benchmark_parity import LOCUS_V1_BENCHMARKS


@pytest.mark.parametrize(
    "name, config_path",
    LOCUS_V1_BENCHMARKS,
    ids=[name for name, _ in LOCUS_V1_BENCHMARKS],
)
def test_locus_v1_baseline_is_first_preset(name: str, config_path: str) -> None:
    data = yaml.safe_load(Path(config_path).read_text())
    presets = data.get("presets")
    assert isinstance(presets, list) and presets, (
        f"{config_path}: expected a non-empty `presets:` list"
    )
    assert presets[0] == "locus.v1_baseline", (
        f"{config_path}: `locus.v1_baseline` must be the first preset "
        f"(got {presets!r}). Scenario-specific presets must compose AFTER "
        "the baseline so they can override shared defaults."
    )
