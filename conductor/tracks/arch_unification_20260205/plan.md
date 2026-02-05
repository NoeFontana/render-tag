# Implementation Plan: Architectural Unification & Codebase Simplification

## Phase 1: Centralized Blender Bridge [checkpoint: e1c0cbc]
Establishing the "Service Locator" to centralize Blender dependencies and eliminate mocking boilerplate.

- [x] **Task: Create `src/render_tag/backend/bridge.py` (The Provider)** (4888ec8)
    - [x] Implement a singleton-based provider that automatically serves mocks when `blenderproc` is unavailable.
    - [x] Centralize `bpy`, `bproc`, and `mathutils` imports.
- [x] **Task: Refactor Backend Modules to use Bridge** (946e054)
    - [x] Update `scene.py`, `assets.py`, `camera.py`, `projection.py`, and `layouts.py`.
    - [x] Remove all `try/except ImportError` blocks and `setup_mocks` functions.
- [x] **Task: Write Tests for Bridge Auto-Mocking** (4888ec8)
    - [x] Verify that importing from the bridge in a standard Python environment serves the correct mock objects.
- [x] **Task: Conductor - User Manual Verification 'Centralized Blender Bridge' (Protocol in workflow.md)** (e1c0cbc)

## Phase 2: Unified Worker Orchestration [checkpoint: 126490a]
Consolidating 'Cold' and 'Hot' execution into a single, ZMQ-driven "Worker" abstraction.

- [x] **Task: Refactor `zmq_server.py` for Dual-Mode Execution** (f7e196b)
    - [x] Implement an "Ephemeral" mode where the server processes a finite list of recipes and then exits.
- [x] **Task: Create `UnifiedWorkerOrchestrator`** (126490a)
    - [x] Merge logic from `LocalExecutor` and `WorkerPool` into a single Host-side class.
    - [x] Standardize logging and telemetry collection via `TelemetryAuditor`.
- [x] **Task: Retirement of Legacy `LocalExecutor`** (126490a)
    - [x] Update CLI to use the new unified orchestrator for all generation tasks.
- [x] **Task: Conductor - User Manual Verification 'Unified Worker Orchestration' (Protocol in workflow.md)** (126490a)

## Phase 3: Geometry & Renderer Facade
Decoupling the procedural logic from the underlying rendering engine.

- [x] **Task: Pure-Python Geometry Layer** (71fdc1e)
    - [x] Move coordinate transformations and projection math to a library that accepts standard NumPy arrays/lists instead of Blender objects.
- [x] **Task: Renderer Facade Implementation** (3abf18b)
    - [x] Refactor `render_loop.py` to use a high-level `Renderer` interface, hiding the specifics of `blenderproc` initialization and cleanup.
- [ ] **Task: Conductor - User Manual Verification 'Geometry & Logic Decoupling' (Protocol in workflow.md)**

## Phase 4: Final Cleanup & Validation
Removing redundant code and validating the simplified architecture.

- [ ] **Task: Codebase-wide Retirement of Boilerplate**
    - [ ] Remove `executor.py` and any remaining `setup_mocks` references.
- [ ] **Task: Comprehensive Integration Benchmark**
    - [ ] Compare performance of the Unified Orchestrator against the previous benchmarks to ensure zero regression.
- [ ] **Task: Conductor - User Manual Verification 'Final Cleanup & Validation' (Protocol in workflow.md)**
