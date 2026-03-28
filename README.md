# render-tag

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**render-tag** is a high-performance procedural 3D synthetic data generator for fiducial markers (AprilTag, ArUco) and calibration boards (ChArUco, AprilGrid). It enables robust detector evaluation and high-fidelity training data generation with sub-pixel accurate ground truth.

---

## Key Features

*   **Procedural 3D Scenes**: Randomized lighting, materials, HDRI backgrounds, and camera trajectories for diverse training scenarios.
*   **High-Performance Orchestration**: A decoupled **Host-Backend** architecture utilizing a **ZMQ-based Hot Loop** to minimize Blender execution overhead.
*   **Calibration Grade**: Sub-pixel accurate projections strictly aligned with OpenCV continuous coordinates to eliminate projection bias.
*   **Comprehensive Annotations**: Automated generation of COCO JSON, OpenCV CSV, and "Rich Truth" metadata including PPM, depth maps, poses, and lighting parameters.
*   **Unified CLI**: A modular command-line interface for data generation, validation, visualization, and dataset auditing.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/NoeFontana/render-tag.git
cd render-tag

# Install dependencies using uv
uv sync

# Install BlenderProc (Required for 3D generation)
uv run pip install blenderproc
```

---

## Quick Start

```bash
# 1. Synchronize assets (HDRIs and textures) from Hugging Face Hub
uv run render-tag hub pull-assets

# 2. Validate the configuration file
uv run render-tag validate-config --config configs/default.yaml

# 3. Generate a sample dataset (10 scenes)
uv run render-tag generate --config configs/default.yaml --output output/sample --scenes 10

# 4. Visualize the generated annotations
uv run render-tag viz dataset --output output/sample
```

---

## Architecture

`render-tag` employs a high-concurrency **Host-Backend** architecture:

*   **Host (Python >=3.11)**: Pure Python logic for procedural mathematics, scene recipe generation, and worker orchestration. The host environment remains isolated from Blender-specific dependencies.
*   **Backend (Blender/ZMQ)**: Optimized Blender workers executing a persistent loop. This design significantly reduces latency by avoiding the overhead of repeated Blender process initialization.

Detailed design documentation is available in the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)**.

---

## Documentation

*   **[User Guide](https://noefontana.github.io/render-tag/guide/)**: Comprehensive documentation on CLI commands, configuration schema, and workflows.
*   **[Coordinate Systems](https://noefontana.github.io/render-tag/coordinates/)**: Specifications for poses, image coordinates, and data standards.
*   **[API Reference](https://noefontana.github.io/render-tag/api/)**: Detailed technical documentation for core modules and interfaces.

---

## Development

```bash
# Install development dependencies
uv sync --all-groups

# Execute test suite
uv run pytest tests/ -v

# Perform linting and type checking
uv run ruff check src/
uv run ty check
```

---

## Contributing

Contributions are welcome. Please review the **[CONTRIBUTING.md](CONTRIBUTING.md)** file and the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)** prior to submitting a pull request.

## License

This project is licensed under the MIT License. Refer to the **[LICENSE](LICENSE)** file for the full text.
