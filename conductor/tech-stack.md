# Technology Stack

## Core Language & Runtime
- **Python 3.12:** Utilizing modern features like type hinting and the latest standard library improvements.
- **uv:** Fast Python package installer and resolver used for dependency management and environment isolation.

## 3D Rendering & Computer Vision
- **Blender:** The primary 3D engine used for high-fidelity rendering and procedural scene generation.
- **BlenderProc (v2.8.0+):** A modular pipeline for generating photorealistic datasets, used as the primary interface for Blender.
- **OpenCV (opencv-contrib-python):** Used for computer vision tasks, including tag detection validation and image processing.
- **Hugging Face Hub:** Used as the remote Object Store for binary asset management and synchronization.

## Data Management & Infrastructure
- **Pydantic (v2):** Used for strict data validation and settings management. All internal schemas and "Scene Recipes" are defined using Pydantic models.
- **Typer:** Powering the CLI interface, providing a user-friendly and type-safe way to interact with the generation pipeline.
- **Docker:** Supported as a pluggable execution engine for hermetic and reproducible rendering environments.
- **PyYAML:** Used for handling configuration files and experiment definitions.
- **Pillow:** Utilized for basic image manipulation and processing within the pipeline.

## Development & Quality Assurance
- **Pytest:** The primary testing framework for unit and integration tests.
- **Ruff:** Used for extremely fast linting and code formatting, ensuring adherence to project standards.
- **Mypy/Ty:** Employed for static type checking to catch errors early and improve codebase maintainability.
