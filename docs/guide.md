# User Guide

This guide covers the usage of `render-tag` for generating synthetic fiducial marker datasets.

## CLI Interface

The primary entry point is the `render-tag` command.

### Generate Data

```bash
uv run render-tag generate [OPTIONS]
```

**Common Options:**

- `-c, --config PATH`: Path to config YAML file [default: `configs/default.yaml`]
- `-o, --output PATH`: Output directory [default: `output/dataset_01`]
- `-n, --scenes INTEGER`: Number of scenes to generate [default: 1]
- `-w, --workers INTEGER`: Number of parallel workers [default: 1]
- `-v, --verbose`: Enable verbose output from BlenderProc
- `-e, --executor TEXT`: Execution engine: `local`, `docker`, `mock` [default: `local`]

---

### Dataset Auditing

The `audit` command group provides tools for analyzing dataset quality and performance.

#### Run Audit
Analyze a dataset's geometric distribution and integrity.
```bash
uv run render-tag audit run --dir output/dataset_01
```

#### Diff Datasets
Compare two datasets to detect drift or regressions.
```bash
uv run render-tag audit diff --base output/baseline --experimental output/variant_a
```

---

### Configuration

`render-tag` uses YAML for configuration. The configuration is divided into several sections.

### Dataset Section

Controls the global seed and output scale.

```yaml
dataset:
  seed: 42
  num_scenes: 100
```

### Camera Section

Defines the sensor parameters and sampling bounds.

```yaml
camera:
  resolution: [1920, 1080]
  fov: 60.0
  samples_per_scene: 10
  min_distance: 1.0
  max_distance: 5.0
```

### Tag Section

Specifies the marker family and material properties.

```yaml
tag:
  family: tag36h11
  size_meters: 0.1
  material:
    randomize: true
    roughness_min: 0.1
    roughness_max: 0.5
```

### Renderer Section (CV-Safe Strategy)

The `renderer` section controls the 3D engine's performance and quality trade-offs. `render-tag` defaults to a "CV-Safe" strategy that uses adaptive sampling and guided denoising to maximize throughput without sacrificing corner accuracy.

```yaml
renderer:
  mode: cycles
  # Adaptive sampling termination criteria
  noise_threshold: 0.05
  # Hard limit on samples per pixel
  max_samples: 128
  # Guided denoising (Intel OIDN + Albedo/Normal guidance)
  enable_denoising: true
```

| Parameter | Default | CV-Safe Recommendation |
|-----------|---------|------------------------|
| `noise_threshold` | 0.05 | 0.02 (High Precision) to 0.1 (Draft) |
| `max_samples` | 128 | 64 - 256 |
| `enable_denoising` | true | Always `true` for CV speedup |

---

### Layout Modes

`render-tag` supports three layout modes:

1.  **Plain**: Tags scattered randomly on a floor.
2.  **ChArUco (cb)**: Checkerboard pattern compatible with OpenCV calibration.
3.  **AprilGrid**: Dense grid compatible with Kalibr.

## Advanced Generation

### Sharding and Parallelism

For large datasets, `render-tag` can distribute work across multiple processes or shards.

```bash
# Run with 8 parallel workers on a single machine
uv run render-tag generate --workers 8 --scenes 1000

# Run a specific shard (e.g., shard 2 of 10)
uv run render-tag generate --total-shards 10 --shard-index 2
```

### Resuming Work

If a render is interrupted, use the `--resume` flag to skip already completed scenes by checking the sidecar metadata:

```bash
uv run render-tag generate --resume --output output/dataset_01
```

---

## Controlled Experiments

The `experiment` command allows you to run parameter sweeps (e.g., testing how detector accuracy changes with distance or motion blur).

```bash
uv run render-tag experiment run --config configs/experiments/glossy_tags.yaml
```

Experiment configs define `sweeps` that override base configuration values, generating a separate sub-dataset for each variant.

---

## Dataset Auditing

After generation, you can audit the dataset to ensure quality and analyze performance:

```bash
# Generate an audit report and dashboard
uv run render-tag audit run --dir output/dataset_01

# Compare two datasets (e.g., baseline vs. experimental)
uv run render-tag audit diff --base output/baseline --experimental output/variant_a
```

The auditor checks for:
- **Visibility:** Are markers actually visible or occluded?
- **Pose Diversity:** Are we covering a sufficient range of angles and distances?
- **Telemetry:** Blender performance metrics (VRAM usage, render times).

---

## Validation

Before starting a long render, you can validate your configuration:

```bash
uv run render-tag validate-config --config configs/default.yaml
```

## Visualization

To verify your generated data, use the `viz` command:

### 2.D Overlays (Standard)
Generates static PNGs with bounding box and keypoint overlays.

```bash
uv run render-tag viz dataset --output output/dataset_01
```

### Interactive Visualization (FiftyOne)
Launches a Voxel51 FiftyOne dashboard for deep dataset inspection.

```bash
uv run render-tag viz fiftyone --dataset output/dataset_01
```

**Key Debugging Capabilities:**
- **Saved Views:** Use the **"Anomalies"** view to instantly filter for samples with `ERR_OOB`, `ERR_OVERLAP`, or `ERR_SCALE_DRIFT` tags.
- **Labeled Corners:** Keypoints are labeled `0`, `1`, `2`, `3` to allow instant verification of the **Orientation Contract** (CW winding from TL) defined in [coordinates.md](coordinates.md).
- **3D Axes:** Visualizes X (Red), Y (Green), and Z (Blue) coordinate axes at the tag center using relative pose metadata.
- **Metadata Filtering:** Use the sidebar sliders to filter samples by `ppm`, `distance`, or `angle_of_incidence`.

---

## Development

`render-tag` is designed for high-signal engineering and clear artifact management.

### Testing and Debugging

To keep the project root clean, all test artifacts and debug data generated by `pytest` are automatically redirected to the gitignored `output/test_results/` directory.

```bash
# Run all tests
uv run pytest

# Inspect test artifacts
ls output/test_results/
```

This behavior is controlled by the `pytest_configure` hook in `tests/conftest.py`. When writing new tests, always use the `tmp_path` fixture to ensure artifacts are correctly isolated and routed.

### Linting and Type Checking

The project enforces strict coding standards via `ruff` and `ty`.

```bash
# Run linter and formatter
uv run ruff check . --fix
uv run ruff format .

# Run static type analysis
uv run ty check
```

---

## Hugging Face Hub Integration

`render-tag` provides first-class support for managing datasets and binary assets on the Hugging Face Hub. This is powered by the `render-tag hub` command group.

### Managing Binary Assets

The `assets/` directory (HDRIs, Textures, Tags) is decoupled from the source code. You can synchronize these with a central asset repository:

```bash
# Pull assets from the default repository
uv run render-tag hub pull-assets

# Push local additions or changes
uv run render-tag hub push-assets -m "Add custom floor textures"
```

> [!TIP]
> You can override the default repository or local directory using `--repo-id` and `--local-dir`.

### Dataset Management (Parquet)

Generated datasets can be uploaded as compressed Parquet subsets. This allows for versioned, config-specific benchmarking without polluting the source tree.

#### Push a Dataset
```bash
uv run render-tag hub push-dataset \
    output/locus_v1/tag16h5 \
    NoeFontana/render-tag-bench \
    --config-name tag16h5
```

#### Pull and Restore
Downloads a Parquet subset and reconstructs the native `render-tag` directory structure (images + `_meta.json` sidecars):

```bash
uv run render-tag hub pull-dataset \
    NoeFontana/render-tag-bench \
    ./restored_data \
    --config-name tag16h5
```

