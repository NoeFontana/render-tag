# Benchmarking

`render-tag` includes utilities to track the performance of the generation pipeline and predefined experiments to benchmark detector performance.

## Standard Benchmarking Datasets

The project defines several "Gold Standard" datasets used for cross-version performance tracking (The Locus Bench). These are the most important datasets for ensuring detector stability.

| Dataset Name | Config Path | Focus |
|--------------|-------------|-------|
| **Locus Pose Baseline** | `configs/experiments/locus_pose_baseline.yaml` | Pose estimation stability under distance and angle sweeps. |

## Generating Benchmark Datasets

Benchmark datasets are defined as experiments and should be run using the `experiment run` command.

### 1. Fast Verification (Workbench)
Use the `workbench` renderer for rapid logic verification or if you only need bounding boxes without photorealistic noise.
```bash
uv run render-tag experiment run --config configs/experiments/locus_pose_baseline.yaml --renderer-mode workbench
```

### 2. Production Baseline (Cycles)
Generate high-fidelity data for training or final verification using the `cycles` renderer. Use `--workers` to parallelize the generation.
```bash
uv run render-tag experiment run --config configs/experiments/locus_pose_baseline.yaml --workers 4 --renderer-mode cycles
```

### 3. Uploading Resulting Subsets

After a benchmark generation completes, the results should be pushed to the Hugging Face Hub as a versioned subset:

```bash
uv run render-tag hub push-dataset \
    output/locus_pose_v1 \
    NoeFontana/render-tag-bench \
    --config-name pose_baseline_v1
```


## Dataset Auditing & Quality Gates

After a benchmark generation completes, use the `audit` command to verify quality and check for statistical drift.

### 1. Run Audit
Generates a comprehensive quality report, including geometric coverage and integrity checks.
```bash
uv run render-tag audit run --dir output/locus_pose_v1
```

### 2. Compare Datasets (Drift Detection)
Compare two datasets to detect performance regressions or distribution shifts.
```bash
uv run render-tag audit diff --base output/baseline --experimental output/variant_a
```

## Performance Tracking & Telemetry

`render-tag` includes a built-in telemetry system that monitors worker health and rendering throughput in real-time.

### Automated Collection
The `UnifiedWorkerOrchestrator` automatically collects telemetry from all active workers. This data is used for:
- **Resource Guarding:** Automatically restarting workers if VRAM exceeds thresholds.
- **Throughput Analysis:** Measuring renders-per-second and total execution time.

### Analysis
Telemetry is typically saved as `telemetry.csv` in the dataset output directory. You can analyze this data using the `TelemetryAuditor` or by inspecting the summary in the `audit` command output.

```python
from render_tag.audit.auditor import TelemetryAuditor

auditor = TelemetryAuditor()
# ... (Orchestrator adds entries during run) ...
auditor.save_csv(Path("output/dataset_01/telemetry.csv"))
```

## Optimizations

`render-tag` implements several performance optimizations:

- **ZMQ Hot Loop**: Persistent workers avoid Blender startup overhead.
- **Mesh Pooling**: Blender objects are reused across scenes.
- **Lazy Assets**: HDRIs and textures are cached in VRAM.
