# Specification: Architectural Unification & Codebase Simplification

## Overview
As the project scales, the divergence between 'Cold' and 'Hot' execution paths and the proliferation of mocking boilerplate have become maintenance risks. This track unifies all rendering under a single "Worker" abstraction and introduces a centralized "Blender Provider" to decouple core logic from the 3D engine.

## Functional Requirements

### 1. Unified Worker Execution
- Standardize all Blender execution on the `zmq_server.py` entry point.
- Refactor `LocalExecutor` to launch a short-lived "Ephemeral Worker" that processes one batch and exits, using the same ZMQ protocol as the persistent `WorkerPool`.
- Consolidate logging, telemetry, and error handling into a single Host-side `WorkerOrchestrator`.

### 2. Dependency Injection Container (Blender Bridge)
- Create a centralized `src/render_tag/backend/bridge.py` that acts as a Service Locator for Blender APIs.
- Backend modules will import `bproc` and `bpy` from this bridge.
- The bridge will automatically serve high-fidelity Mocks when Blender is unavailable, controlled by a single environment variable or initialization call.

### 3. Backend Adapter Pattern
- Refactor `render_loop.py` to use a high-level `Renderer` interface (Facade pattern).
- Decouple procedural math and coordinate transformations into a pure-Python `geometry` layer that has zero dependencies on `bpy` or `blenderproc`.

### 4. Protocol Consolidation
- Align the `SceneRecipe` JSON schema strictly with the ZMQ `RENDER` payload to ensure a single, consistent "Contract of Trust" across all execution modes.

## Non-Functional Requirements
- **Maintainability**: Reduce total lines of backend code by ~20% by removing boilerplate.
- **Scalability**: Enable seamless swapping of rendering engines (e.g., Blender to a faster custom rasterizer for specific tests) without touching core logic.
- **Testability**: 100% of core rendering logic should be unit-testable in standard Python environments without complex mock injection.

## Acceptance Criteria
- [ ] `executor.py` is retired or reduced to a minimal wrapper around the ZMQ worker.
- [ ] All `try/except ImportError: bproc = None` blocks are removed from backend modules.
- [ ] `setup_mocks` functions are removed from all modules.
- [ ] A single integration test confirms both "Ephemeral" and "Persistent" modes work using the same orchestration logic.
