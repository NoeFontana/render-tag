# render-tag

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**render-tag** is a procedural 3D synthetic data generator for fiducial markers (AprilTag, ArUco) and calibration boards (ChArUco, AprilGrid). It is designed to bridge the gap between idealized 2D simulations and real-world optical distortions by utilizing high-fidelity 3D rendering.

---

## Key Features

*   **Procedural Scene Generation**: Randomized lighting, materials, HDRI backgrounds, and camera trajectories to ensure robust detector training.
*   **Parallel Worker Orchestration**: Utilizes a persistent pool of Blender subprocesses to eliminate the multi-second overhead of repeated process initialization.
*   **ZMQ-Based Hot Loop**: Communication between the Python host and Blender backend is handled via ZeroMQ, allowing for efficient task dispatching and state persistence.
*   **Sub-Pixel Precision**: strictly aligned with OpenCV continuous coordinates (eliminating the common 0.5px centering bias) for calibration-grade ground truth.
*   **Extensible Annotations**: Generates COCO JSON, OpenCV-compatible CSVs, and "Rich Truth" metadata including per-pixel depth, 6DoF poses, and lighting parameters.
*   **Modular CLI**: A single entry point for configuration validation, data generation, 2D/3D visualization, and dataset quality auditing.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/NoeFontana/render-tag.git
cd render-tag

# Install core dependencies
uv sync

# Install BlenderProc (Required for the 3D rendering backend)
uv run pip install blenderproc
```

---

## Quick Start

```bash
# 1. Pull environment assets (HDRIs and textures) from Hugging Face Hub
uv run render-tag hub pull-assets

# 2. Validate your configuration file
uv run render-tag validate-config --config configs/default.yaml

# 3. Generate a sample dataset
uv run render-tag generate --config configs/default.yaml --output output/sample --scenes 10

# 4. Visualize the generated dataset
uv run render-tag viz dataset --output output/sample
```

---

## Architecture

`render-tag` uses a **Host-Backend** separation to maximize throughput:

*   **Host (Python >=3.11)**: Handles procedural math, scene recipe generation, and manages a pool of workers. It is completely decoupled from Blender's Python API (`bpy`).
*   **Backend (Blender/BlenderProc)**: Persistent worker processes that listen for render commands over ZMQ. By keeping Blender open in a "Hot Loop," the system avoids the significant latency of restarting the 3D engine for every frame.

The system scales linearly with available CPU cores and GPU VRAM by spawning multiple parallel workers, each assigned to a unique communication port.

For technical details, see the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)**.

---

## Documentation

*   **[User Guide](https://noefontana.github.io/render-tag/guide/)**: CLI commands, configuration schema, and generation workflows.
*   **[Coordinate Systems](https://noefontana.github.io/render-tag/coordinates/)**: Detailed specifications for camera models, poses, and image standards.
*   **[API Reference](https://noefontana.github.io/render-tag/api/)**: Technical documentation for developers extending the generator.

---

## Development

```bash
# Install development and testing dependencies
uv sync --all-groups

# Run the test suite
uv run pytest tests/ -v

# Static analysis and type checking
uv run ruff check src/
uv run ty check
```

---

## Contributing

Please review **[CONTRIBUTING.md](CONTRIBUTING.md)** and the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)** before submitting pull requests.

## License

MIT License. See **[LICENSE](LICENSE)** for details.
