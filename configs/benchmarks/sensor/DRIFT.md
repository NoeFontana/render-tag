# Sensor-Realism Drift Gate

This file is the contract for the sensor-realism drift gate. The gate is a
pytest parametrized over every sensor benchmark in this directory — it
compiles the PR's config through `SceneCompiler`, diffs the resulting
`SceneRecipe` against a pinned JSON fixture, and fails on any semantic
mismatch.

No rendering happens in CI. A pixel-level backend regression (e.g., a typo
in the tone-mapping curve) is caught by the unit tests under
`tests/unit/heavy_logic/simulation/` instead. The drift gate exists for the
larger class of silent bugs: a schema field stops plumbing through, a
preset override gets lost, an ISO-coupling edge case falls through.

## How it works

- **Pinned fixtures**: `tests/fixtures/sensor_drift/<benchmark>_scene_<id>.json`
  — compiled-recipe snapshots for `(seed=42, scene_id in (0, 1, 5))` per
  benchmark.
- **Test**: `tests/unit/heavy_logic/generation/test_sensor_drift.py` runs
  in the normal pytest suite (no separate CI job — it piggybacks on the
  existing "Automated Tests (Pytest)" task).
- **Diff tolerance**: `diff_recipes` (from `tests/fixtures/compiler_parity/`)
  compares floats with `rel_tol=abs_tol=1e-13`. Real semantic drift moves
  values by orders of magnitude beyond that; last-bit runtime noise does
  not trip the gate.

## Intentional changes — the loop

When a PR intentionally changes pixel intent (new preset, schema field,
compiler path), the drift-gate test will fail. Resolve it in the same PR:

```bash
uv run python scripts/capture_sensor_drift_fixtures.py
git add tests/fixtures/sensor_drift/
```

The PR description must explain the delta and why it is not a regression.
A reviewer reads the fixture diff alongside the code change.

## Covered benchmarks

| Benchmark                      | Config                                                           |
| ------------------------------ | ---------------------------------------------------------------- |
| `locus_v1_high_iso`            | `configs/benchmarks/sensor/locus_v1_high_iso.yaml`               |
| `locus_v1_low_dr_outdoor`      | `configs/benchmarks/sensor/locus_v1_low_dr_outdoor.yaml`         |
| `locus_v1_raw_pipeline`        | `configs/benchmarks/sensor/locus_v1_raw_pipeline.yaml`           |

Adding a new sensor benchmark: append to `BENCHMARK_CONFIGS` in
`tests/fixtures/sensor_drift/__init__.py`, run the capture script, commit
the new fixtures.

## Why recipe-diff (and not pixel-diff / audit-diff)

- **Pixel-diff** would require rendering ≥50 scenes at 1920×1080 on each PR.
  GitHub-hosted runners don't ship Blender; installing it + rendering would
  bust the CI time budget by an order of magnitude.
- **Audit-diff** (the `AuditDiff` extension in `src/render_tag/audit/auditor.py`)
  requires rendered output to run its geometric/integrity checks. Same cost.
  The `AuditDiff` extension lands in this phase for local / manual use —
  run it by hand when you want a richer signal than the recipe can give.
- **Recipe-diff** catches any bug that corrupts the SceneCompiler's output
  — the exact surface that historically hid "cosmetic field" bugs (ISO,
  tone_mapping, dynamic_range_db before Phase 1/2 wiring). It costs <2s.

## Phase 3 backlog

- `detection_rate` and `reprojection_error` are not yet computed by the
  audit pipeline; `AuditDiff.calculate()` cannot surface them until a tag
  detector (opencv aruco / apriltag) runs on rendered images. This is the
  right Phase 3 unit: once the `AuditReport` fields exist, extending
  `AuditDiff` is mechanical.
- Pixel-level CI (rendering a single low-res canary scene per PR) becomes
  attractive once `detection_rate_diff` exists and Blender lands on the
  runner. Today, the combined cost/benefit doesn't justify it.
