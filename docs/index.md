# render-tag

Procedural 3D synthetic data generation for fiducial marker (AprilTag/ArUco) detector training.

`render-tag` is a robust pipeline for generating high-fidelity synthetic datasets. It uses Blender and BlenderProc to create photorealistic renders with precise ground truth annotations.

## Installation

```bash
# Clone the repository
git clone https://github.com/NoeFontana/render-tag.git
cd render-tag

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
uv run render-tag validate-config --config configs/default.yaml

# Generate synthetic data (requires BlenderProc)
uv run render-tag generate --config configs/default.yaml --output output/dataset_01 --scenes 10

# Visualize detection annotations
uv run render-tag viz dataset --output output/dataset_01
```

## Documentation Structure

- [User Guide](guide.md): Detailed configuration and usage instructions.
- [Architecture](architecture.md): Overview of the generation pipeline and backend.
- [Coordinate Systems](coordinates.md): Definition of camera and tag spaces.
- [API Reference](api.md): Auto-generated documentation from source code.
