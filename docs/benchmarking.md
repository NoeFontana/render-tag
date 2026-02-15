# Benchmarking

`render-tag` includes utilities to track the performance of the generation pipeline and predefined experiments to benchmark detector performance.

## Standard Benchmarking Datasets

The project defines several "Gold Standard" datasets used for cross-version performance tracking (The Locus Bench). These are the most important datasets for ensuring detector stability.

| Dataset Name | Config Path | Focus |
|--------------|-------------|-------|
| **Locus Bench Phase 1** | `configs/experiments/locus_bench_p1.yaml` | Calibration accuracy and ground truth consistency. |
| **Locus Pose Baseline** | `configs/experiments/locus_pose_baseline.yaml` | Pose estimation stability under distance and angle sweeps. |

## Generating Benchmark Datasets

Benchmark datasets are defined as experiments and should be run using the `experiment run` command.

### 1. Fast Verification (Workbench)
Use the `workbench` renderer for rapid logic verification or if you only need bounding boxes without photorealistic noise.
```bash
uv run render-tag experiment run --config configs/experiments/locus_bench_p1.yaml --renderer-mode workbench
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


## Performance Tracking

The `Benchmarker` utility is used internally to measure the duration of different pipeline stages.

```python
from render_tag.common.benchmarking import Benchmarker

bench = Benchmarker("My Generation Run")
with bench.measure("Scene Generation"):
    # ... logic ...
    pass

bench.report.log_summary()
```

The performance summary includes breakdown of:
- Scene recipe generation
- Blender context stabilization
- Rendering time per frame
- VRAM usage and telemetry

## Optimizations

`render-tag` implements several performance optimizations:
- **ZMQ Hot Loop**: Persistent workers avoid Blender startup overhead.
- **Mesh Pooling**: Blender objects are reused across scenes.
- **Lazy Assets**: HDRIs and textures are cached in VRAM.
