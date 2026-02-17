# Technology Stack

## Core Language & Runtime
- **Python 3.11:** Utilizing modern features while ensuring perfect parity with Blender's internal Python environment.
- **uv:** Fast Python package installer and resolver used for dependency management and environment isolation.

## 3D Rendering & Computer Vision
- **Blender:** The primary 3D engine used for high-fidelity rendering and procedural scene generation.
- **BlenderProc (v2.8.0+):** A modular pipeline for generating photorealistic datasets, used as the primary interface for Blender.
- **Guided Denoising (OIDN):** Intel OpenImageDenoise with Albedo and Normal guidance for high-efficiency, edge-preserving renders.
- **Asset Management:** Object pooling and material recycling strategies within Blender to optimize VRAM usage and rendering speed.
- **OpenCV (opencv-contrib-python):** Used for computer vision tasks, including tag detection validation and image processing.
- **Hugging Face Hub:** Used as the remote Object Store for binary asset management and synchronization.
- **COCO Format:** Standard annotation format for object detection, segmentation, and keypoint estimation (corners).
- **Quaternion Math:** Scalar-first (wxyz) orientation representation for geodesic error stability.

## Data Management & Infrastructure
- **Pydantic (v2):** Used for strict data validation and settings management. All internal schemas and "Scene Recipes" are defined using Pydantic models.
- **Schema Migration Engine:** Centralized migrator for automatic upgrading of legacy configurations (YAML/JSON) to current standards, preserving backward compatibility.
- **Pure Execution Backend:** Rendering architecture where workers are stateless and receive absolute, rigid instructions, eliminating "Zombie Logic" and ensuring perfect sim-to-sim parity.
- **Cryptographic Fingerprinting (hashlib):** SHA256-based content addressing for jobs, environment states, and binary assets to ensure data integrity and provenance.
- **Typer:** Powering the CLI interface, providing a user-friendly and type-safe way to interact with the generation pipeline.
- **Resilient Orchestration:** Shard-based parallel rendering with automated state validation, smart resumption, and dynamic resource (RAM) auto-tuning for cross-platform stability.
- **Bootstrap Pattern:** Environment-aware initialization module (`bootstrap.py`) that synchronizes Blender's Python runtime with the project's virtual environment, ensuring dependency parity and strict isolation.
- **Structured Observability (NDJSON)**: High-performance IPC protocol using Newline Delimited JSON and `orjson` for real-time telemetry, progress tracking, and log routing between Backend and Host.
- **Polars:** High-performance, multi-threaded DataFrame library used for vectorized dataset auditing and KPI calculation.
- **Goal-Oriented Sampling:** Mathematical solvers for goal-oriented pose generation (e.g., target PPM) ensuring statistical balance in generated datasets.
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
- **fake-bpy-module**: High-fidelity static type stubs for Blender and mathutils, enabling robust static analysis and IDE autocompletion.
