# render-tag

Procedural 3D synthetic data generation for fiducial marker (AprilTag/ArUco) and fiducial board ChArUco/AprilGrid detector evaluation or training.

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

# Synchronize assets from Hugging Face
uv run render-tag hub pull-assets
```

## Architecture

`render-tag` uses a decoupled **Host-Backend** architecture for high-performance rendering:

*   **Host (Python >=3.11)**: Procedural math, recipe generation, and worker orchestration.
*   **Backend (Blender/ZMQ)**: Persistent 3D workers running a **ZMQ-based Hot Loop**. This avoids the massive overhead of Blender startup.

👉 For detailed design notes, see **[Architecture Guide](docs/architecture.md)**.

## Usage

### CLI Commands

The primary way to interact with `render-tag` is through its modular CLI.

```bash
# Generate synthetic data
uv run render-tag generate --config configs/default.yaml --scenes 100

# Visualize detection annotations
uv run render-tag viz dataset --output output/dataset_01

# Audit dataset quality
uv run render-tag audit run --dir output/dataset_01
```

👉 See the **[User Guide](docs/guide.md)** for a full list of commands and options.

### Configuration

`render-tag` uses YAML for flexible scene definition. Ready-to-use presets are available in `configs/presets/`.

👉 See **[Configuration Details](docs/guide.md#configuration)** and **[Coordinate Standards](docs/coordinates.md)** for data layout info.

## Output Format

Generated datasets include images and standardized annotations:

- `tags.csv`: Merged corner annotations (OpenCV convention).
- `annotations.json`: Merged COCO format annotations.
- `rich_truth.json`: Extended metadata (pose, PPM, lighting).
- `provenance.json`: Master manifest mapping images to their exact `SceneRecipe`.

👉 See **[Coordinate Systems & Data Standards](docs/coordinates.md)** for detailed field definitions.

## Development

```bash
# Install dev dependencies
uv sync --all-groups

# Run tests
uv run pytest tests/ -v

# Run linting and type checking
uv run ruff check src/
uv run ty check
```

## License

MIT License
