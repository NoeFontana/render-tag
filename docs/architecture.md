# Architecture

`render-tag` follows a strictly decoupled architecture to ensure that generation logic is independent of the rendering engine.

## High-Level Overview

The system is divided into **Host** code (Python 3.12) and **Backend** code (Blender/BlenderProc).

```mermaid
graph TD
    A[CLI / Python API] --> B[Generator]
    B --> C[Scene Recipe JSON]
    C --> D[Executor]
    D --> E[BlenderProc / Blender]
    E --> F[Rendered Images]
    E --> G[Metadata Sidecars]
    F --> H[Post-Processor]
    G --> H
    H --> I[Final Dataset]
```

## Components

### 1. Core (`src/render_tag/core/`)
The foundation of the system. Contains the single source of truth **Schemas** (Pydantic models), configuration logic, and fundamental utilities like resilience and resource management.

### 2. Generation (`src/render_tag/generation/`)
Pure Python procedural logic. Samples parameters (camera poses, lighting, tag IDs) and builds `SceneRecipe` objects. It has **no** dependency on Blender, allowing for fast "Shadow Renders" (2D bounding box verification without 3D).

### 3. Backend (`src/render_tag/backend/`)
The 3D rendering engine. It consumes a `SceneRecipe` and uses `BlenderProc` via `backend/engine.py` to build the scene. This code runs exclusively inside the Blender Python environment.

### 4. Orchestration (`src/render_tag/orchestration/`)
The `UnifiedWorkerOrchestrator` manages the lifecycle of `PersistentWorkerProcess` instances. It handles ZMQ communication, VRAM guardrails, and parallel sharding.

### 5. Data I/O (`src/render_tag/data_io/`)
Handles asset loading, caching, and writing final annotations (COCO, CSV).

## The "Hot Loop" (Persistent Workers)

To avoid the significant overhead of starting Blender for every scene, `render-tag` uses a persistent worker architecture.

1.  **Orchestrator** starts one or more Blender instances in the background.
2.  Each Blender instance runs a **ZMQ Server** (`zmq_server.py`).
3.  The Orchestrator sends **Scene Recipes** over ZMQ.
4.  Blender renders the scene, saves the result, and remains ready for the next recipe without quitting.

This "Hot Loop" can improve rendering throughput by **2-5x** for small scenes.

## Reproducibility

Correctness in synthetic data requires strict reproducibility. `render-tag` ensures this through:

- **Environment Fingerprinting:** We hash the `uv.lock` and record the Blender version. If the environment changes, the system issues a warning or error.
- **Config Hashing:** Every dataset contains a `job.json` (JobSpec) that includes a SHA256 hash of the exact configuration used.
- **Deterministic Sharding:** Seeds are derived from a master seed and shard index, ensuring that scene #500 is identical regardless of whether it was rendered in a single batch or as part of a specific shard.
