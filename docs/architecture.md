# Architecture

`render-tag` follows a strictly decoupled architecture to ensure that generation logic is independent of the rendering engine.

## High-Level Overview

The system is divided into **Host** code (Python 3.11) and **Backend** code (Blender/BlenderProc).

```mermaid
graph TD
    A[CLI / Python API] --> B[Generator]
    B -- SceneRecipe --> C[Unified Orchestrator]
    C -- ZMQ REQ --> D[ZMQ Server (Blender)]
    D --> E[Worker Server]
    E --> F[BlenderBridge]
    F --> G[BlenderProc / Blender]
    G --> H[Rendered Images & Metadata]
```

## Components

### 1. Core (`src/render_tag/core/`)
The foundation of the system. Contains the single source of truth **Schemas** (Pydantic models), configuration logic, and fundamental utilities.

### 2. Generation (`src/render_tag/generation/`)
Pure Python procedural logic. Samples parameters and builds `SceneRecipe` objects. It has **no** dependency on Blender.

### 3. Backend (`src/render_tag/backend/`)
The 3D rendering engine.
- **`bootstrap.py`**: Centralized environment stabilization. Handles paths, venv site-packages, and logging.
- **`bridge.py`**: `BlenderBridge` provides explicit Dependency Injection for Blender/BlenderProc APIs.
- **`worker_server.py`**: Implementation of the "Hot Loop" ZMQ server.
- **`engine.py`**: The actual BlenderProc execution logic.

### 4. Orchestration (`src/render_tag/orchestration/`)
The `UnifiedWorkerOrchestrator` manages the lifecycle of `PersistentWorkerProcess` instances. It handles ZMQ communication, VRAM guardrails, and parallel sharding.

### 5. Data I/O (`src/render_tag/data_io/`)
Handles asset loading, caching, and writing final annotations (COCO, CSV).

## The "Hot Loop" (Persistent Workers)

To avoid the significant overhead of starting Blender for every scene, `render-tag` uses a persistent worker architecture.

1.  **Orchestrator** starts one or more Blender instances in the background.
2.  Each Blender instance runs a **ZMQ Server** (`zmq_server.py`).
3.  The Orchestrator sends **Scene Recipes** over ZMQ.
4.  The **Worker Server** receives the recipe, uses the **BlenderBridge** to access APIs, and renders the scene.
5.  Blender remains ready for the next recipe without quitting.

This "Hot Loop" improves rendering throughput by **2-5x** for small scenes.

This "Hot Loop" can improve rendering throughput by **2-5x** for small scenes.

## Rendering Performance (CV-Safe)

To maximize generation speed while maintaining the high sub-pixel accuracy required for fiducial tag detection, `render-tag` employs several optimization strategies:

### 1. Adaptive Sampling & Denoising
We use Cycles' **Adaptive Sampling** with a noise threshold (default `0.05`) rather than a fixed sample count. This is combined with **Intel OpenImageDenoise (OIDN)** guided by Albedo and Normal passes. This "CV-Safe" approach ensures that flat surfaces render nearly instantaneously while high-frequency edges (like tag corners) receive enough samples to remain sharp and accurate.

### 2. Light Path Optimization
Standard path tracing bounces light many times to achieve artistic realism. For computer vision training, we "min-max" these bounces:
- **Total Bounces (4):** Diminishing returns for CV after 4.
- **Diffuse (2):** Enough for realistic indirect lighting.
- **Glossy (4):** Critical for preserving specular highlights (glare) which are essential for testing detector robustness.
- **Transmission (0):** Disabled unless glass/refraction is explicitly needed.
- **Caustics (Off):** Computationally expensive and irrelevant for tag detection.

## Reproducibility

Correctness in synthetic data requires strict reproducibility. `render-tag` ensures this through:

- **Environment Fingerprinting:** We hash the `uv.lock` and record the Blender version. If the environment changes, the system issues a warning or error.
- **Config Hashing:** Every dataset contains a `job.json` (JobSpec) that includes a SHA256 hash of the exact configuration used.
- **Asset Hashing:** The `JobSpec` includes a SHA256 hash of all external assets (HDRIs, floor textures, tag images) referenced by the job. This prevents "silent" dataset drift when binary assets are updated on disk or on the Hub.
- **Deterministic Sharding:** Seeds are derived from a master seed and shard index, ensuring that scene #500 is identical regardless of whether it was rendered in a single batch or as part of a specific shard.
