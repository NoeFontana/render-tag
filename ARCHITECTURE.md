# System Architecture (v3.0)

`render-tag` is designed as a **Host-Backend** system using ZMQ to bridge the gap between a standard Python environment and Blender's embedded environment.

## High-Level Flow

```mermaid
graph TD
    A[Host CLI] --> B[Generator]
    B --> C[Scene Recipes]
    C --> D[Unified Orchestrator]
    D -- ZMQ (REQ/REP) --> E[Persistent Worker 0]
    D -- ZMQ (REQ/REP) --> F[Persistent Worker N]
    subgraph Blender Process
    E --> G[ZMQ Server]
    G --> H[BlenderProc Engine]
    end
    H --> I[Output Directory]
```

## Core Components

1.  **Host Process (Standard Python)**:
    *   **Orchestration (`orchestration/orchestrator.py`)**: Manages the lifecycle of persistent worker processes. It communicates with workers over ZMQ, monitors health, and handles automatic restarts on failure or VRAM exhaustion.
    *   **Generator (`generator.py`)**: Pure logic component. It defines "Recipes" (`SceneRecipe`) for each scene deterministically. 
    *   **CLI (`cli/main.py`)**: Unified entry point that binds orchestration and generation.

2.  **Backend Process (Blender)**:
    *   **ZMQ Server (`backend/zmq_server.py`)**: A minimal bootstrap script that runs inside Blender. It starts a ZMQ listener and waits for commands.
    *   **Worker Server (`backend/worker_server.py`)**: The "Hot Loop" implementation. It receives recipes, stabilizes the Blender environment via `bridge.py`, and calls the rendering engine.
    *   **Engine (`backend/engine.py`)**: Low-level interaction with `BlenderProc` to actually render the 3D scene and save metadata.

## The "Hot Loop" Contract

The communication between Host and Backend happens over ZMQ using a robust REQ/REP pattern:

- **INIT**: Orchestrator tells the worker to prime its environment (BlenderProc initialization).
- **RENDER**: Orchestrator sends a `SceneRecipe`. The worker renders it and remains alive.
- **STATUS**: Periodic heartbeat and telemetry (VRAM, uptime).
- **SHUTDOWN**: Graceful termination.

This separation allows for high throughput (no Blender startup overhead) and excellent testability (mocking the ZMQ backend).
