# Lighting-Realism Drift Gate

Parallels the sensor drift gate (`configs/benchmarks/sensor/DRIFT.md`). Same
contract, same tolerance, same regenerate-on-intentional-change loop — only
the benchmark list and fixture directory differ.

See `configs/benchmarks/sensor/DRIFT.md` for the full rationale (recipe-diff
vs. pixel-diff, why this piggybacks on the existing pytest step, how to add
a new benchmark).

## Covered benchmarks

| Benchmark                      | Config                                                           |
| ------------------------------ | ---------------------------------------------------------------- |
| `locus_v1_hard_shadows`        | `configs/benchmarks/lighting/locus_v1_hard_shadows.yaml`         |
| `locus_v1_low_key`             | `configs/benchmarks/lighting/locus_v1_low_key.yaml`              |

## Regenerate on intentional change

```bash
uv run python scripts/capture_lighting_drift_fixtures.py
git add tests/fixtures/lighting_drift/
```

Adding a new lighting benchmark: append to `BENCHMARK_CONFIGS` in
`tests/fixtures/lighting_drift/__init__.py`, run the capture script, commit
the new fixtures.
