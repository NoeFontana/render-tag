# render-tag

Procedural 3D synthetic data generation for fiducial marker (AprilTag/ArUco) detector training.

## Installation

```bash
# Clone the repository
git clone https://github.com/NoeFontana/render-tag.git
cd render-tag/render-tag

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### BlenderProc (Required for generation)

For actual data generation, you need BlenderProc:

```bash
pip install blenderproc
```

## Quick Start

```bash
# Check installation status
uv run render-tag info

# Validate a configuration file
uv run render-tag validate --config configs/default.yaml

# Generate synthetic data (requires BlenderProc)
uv run render-tag generate --config configs/default.yaml --output output/dataset_01 --scenes 10

# Visualize detection annotations
uv run render-tag viz --output output/dataset_01
```

## CLI Commands

### `render-tag generate`

Generate synthetic fiducial marker training data.

```bash
uv run render-tag generate [OPTIONS]

Options:
  -c, --config PATH     Path to config YAML file [default: configs/default.yaml]
  -o, --output PATH     Output directory [default: output/dataset_01]
  -n, --scenes INTEGER  Number of scenes to generate [default: 1]
  -v, --verbose         Enable verbose output from BlenderProc
```

### `render-tag validate`

Validate a configuration file without running generation.

```bash
uv run render-tag validate --config configs/default.yaml
```

### `render-tag info`

Show installation information and supported tag families.

```bash
uv run render-tag info
```

### `render-tag viz`

Visualize detection annotations overlaid on rendered images.

```bash
uv run render-tag viz --output output/dataset_01

# Visualize a specific image
uv run render-tag viz --output output/dataset_01 --image scene_0001_cam_0001

# Don't save visualization files
uv run render-tag viz --output output/dataset_01 --no-save
```

## Configuration

Create a YAML configuration file:

```yaml
dataset:
  seed: 42
  num_scenes: 100

camera:
  resolution: [1920, 1080]
  fov: 60.0
  samples_per_scene: 10

tag:
  family: tag36h11  # or DICT_4X4_50 for ArUco
  size_meters: 0.1

physics:
  drop_height: 1.5
  scatter_radius: 0.5
```

### Supported Tag Families

**AprilTag:**
- tag36h11, tag36h10, tag25h9, tag16h5
- tagCircle21h7, tagCircle49h12
- tagCustom48h12, tagStandard41h12, tagStandard52h13

**ArUco (OpenCV):**
- DICT_4X4_50, DICT_4X4_100, DICT_4X4_250, DICT_4X4_1000
- DICT_5X5_50, DICT_5X5_100, DICT_5X5_250, DICT_5X5_1000
- DICT_6X6_50, DICT_6X6_100, DICT_6X6_250, DICT_6X6_1000
- DICT_7X7_50, DICT_7X7_100, DICT_7X7_250, DICT_7X7_1000
- DICT_ARUCO_ORIGINAL

## Output Format

Generated data is saved in the output directory:

```
output/dataset_01/
├── images/
│   ├── scene_0000_cam_0000.png
│   ├── scene_0000_cam_0001.png
│   └── ...
├── tags.csv              # Corner annotations (Locus-compatible)
├── annotations.json      # COCO format annotations
└── visualizations/       # Debug visualizations (from viz command)
```

### CSV Format

```csv
image_id,tag_id,tag_family,x1,y1,x2,y2,x3,y3,x4,y4
scene_0000_cam_0000,0,tag36h11,123.45,67.89,223.45,67.89,223.45,167.89,123.45,167.89
```

Corner order: BL (1), BR (2), TR (3), TL (4) - Counter-clockwise from bottom-left.

## Development

```bash
# Install dev dependencies
uv sync --all-groups

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check src/
```

## License

MIT License
