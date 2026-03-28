# render-tag

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**render-tag** is a high-performance procedural 3D synthetic data generator for fiducial markers (AprilTag, ArUco) and calibration boards (ChArUco, AprilGrid). It enables robust detector evaluation and high-fidelity training data generation with pixel-perfect ground truth.

---

## 🚀 Key Features

*   **Procedural 3D Scenes**: Fully randomized lighting, materials, HDRI backgrounds, and camera trajectories.
*   **High-Performance Orchestration**: A decoupled **Host-Backend** architecture using a **ZMQ-based Hot Loop** to eliminate Blender's startup overhead.
*   **Calibration Grade**: Sub-pixel accurate projections strictly aligned with OpenCV continuous coordinates (no 0.5px bias).
*   **Rich Annotations**: Automatic generation of COCO JSON, OpenCV CSV, and "Rich Truth" (PPM, depth, poses, lighting).
*   **Modular CLI**: A unified tool for generation, validation, visualization, and dataset auditing.

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/NoeFontana/render-tag.git
cd render-tag

# Install with uv (recommended)
uv sync

# Install BlenderProc (Required for 3D generation)
uv run pip install blenderproc
```

---

## ⚡ Quick Start

```bash
# 1. Sync assets (HDRIs/textures) from Hugging Face
uv run render-tag hub pull-assets

# 2. Validate your configuration
uv run render-tag validate-config --config configs/default.yaml

# 3. Generate a dataset (10 scenes)
uv run render-tag generate --config configs/default.yaml --output output/sample --scenes 10

# 4. Visualize the results
uv run render-tag viz dataset --output output/sample
```

---

## 🏗️ Architecture

`render-tag` is built on a high-concurrency **Host-Backend** model:

*   **Host (Python >=3.11)**: Pure Python logic for procedural math, scene recipe generation, and worker orchestration. It NEVER depends on `bpy`.
*   **Backend (Blender/ZMQ)**: Optimized Blender workers running a persistent execution loop. This architecture allows rendering thousands of scenes without the multi-second overhead of repeated Blender process spawns.

👉 For detailed design notes, see the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)**.

---

## 📖 Documentation

*   **[User Guide](https://noefontana.github.io/render-tag/guide/)**: CLI commands, configuration, and standard workflows.
*   **[Coordinate Systems](https://noefontana.github.io/render-tag/coordinates/)**: Standards for poses, image coordinates, and data layout.
*   **[API Reference](https://noefontana.github.io/render-tag/api/)**: Detailed module documentation for developers.

---

## 🧪 Development

```bash
# Install all development dependencies
uv sync --all-groups

# Run tests
uv run pytest tests/ -v

# Run linting and type checking
uv run ruff check src/
uv run ty check
```

---

## 🤝 Contributing

Contributions are welcome! Please see **[CONTRIBUTING.md](CONTRIBUTING.md)** and read the **[Architecture Guide](https://noefontana.github.io/render-tag/architecture/)** before opening a PR.

## 📄 License

MIT License. See **[LICENSE](LICENSE)** for details.
