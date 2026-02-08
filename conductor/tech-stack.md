# Technology Stack

## Core Language & Runtime
- **Python 3.12:** Utilizing modern features like type hinting and the latest standard library improvements.
- **uv:** Fast Python package installer and resolver used for dependency management and environment isolation.

## 3D Rendering & Computer Vision
- **Blender:** The primary 3D engine used for high-fidelity rendering and procedural scene generation.
- **BlenderProc (v2.8.0+):** A modular pipeline for generating photorealistic datasets, used as the primary interface for Blender.
- **Asset Management:** Object pooling and material recycling strategies within Blender to optimize VRAM usage and rendering speed.
- **OpenCV (opencv-contrib-python):** Used for computer vision tasks, including tag detection validation and image processing.
- **Hugging Face Hub:** Used as the remote Object Store for binary asset management and synchronization.

## Data Management & Infrastructure
- **Pydantic (v2):** Used for strict data validation and settings management. All internal schemas and "Scene Recipes" are defined using Pydantic models.
- **Cryptographic Fingerprinting (hashlib):** SHA256-based content addressing for jobs, environment states, and binary assets to ensure data integrity and provenance.
- **Typer:** Powering the CLI interface, providing a user-friendly and type-safe way to interact with the generation pipeline.
- **Dynamic Load Balancing:** A "Batch Stealing" orchestrator model for parallel rendering, supporting fault tolerance and session resuming.
- **Polars:** High-performance, multi-threaded DataFrame library used for vectorized dataset auditing and KPI calculation.
- **Plotly:** Used for generating interactive HTML dashboards for dataset visualization and manual quality review.
- **Docker:** Supported as a pluggable execution engine for hermetic and reproducible rendering environments.
- **ZeroMQ (pyzmq):** High-performance messaging library used for the structured Host-to-Backend command channel.
- **GPUtil:** Utilized for real-time VRAM monitoring and health-check guardrails within the rendering pool.
- **PyYAML:** Used for handling configuration files and experiment definitions.
- **Pillow:** Utilized for basic image manipulation and processing within the pipeline.

## Development & Quality Assurance
- **Pytest:** The primary testing framework for unit and integration tests.
- **Ruff:** Used for extremely fast linting and code formatting, ensuring adherence to project standards.
- **Mypy/Ty:** Employed for static type checking to catch errors early and improve codebase maintainability.
