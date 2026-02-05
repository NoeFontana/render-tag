# Implementation Plan: Hot Loop Optimization (Persistent Backend)

## Phase 1: Communication & Protocol Foundation [checkpoint: 14f47fa]
This phase establishes the ZeroMQ messaging layer and the JSON protocol that will govern Host-Backend interactions.

- [x] **Task: Define ZMQ Message Schemas (Pydantic)** (0f71ca3)
    - [x] Create `src/render_tag/schema/hot_loop.py` for `Command`, `Response`, and `Telemetry` models.
    - [x] Implement `StateHash` calculation logic.
- [x] **Task: Implement ZMQ Host Client** (795197b)
    - [x] Create `src/render_tag/orchestration/zmq_client.py`.
    - [x] Write tests for connection handling and message serialization.
- [x] **Task: Implement ZMQ Backend Server (Skeleton)** (229537c)
    - [x] Create `src/render_tag/backend/zmq_server.py`.
    - [x] Implement basic Loop-back to verify Host-Backend connectivity via `uv run`.
- [x] **Task: Conductor - User Manual Verification 'Communication & Protocol Foundation' (Protocol in workflow.md)** (14f47fa)

## Phase 2: Persistent Worker Lifecycle [checkpoint: 3239e0e]
Implementing the "Resilient Managed Pool" logic to launch, monitor, and recycle Blender processes.

- [x] **Task: Implement `PersistentWorkerProcess` Manager** (521238d)
    - [x] Logic for spawning Blender subprocesses with ZMQ arguments.
    - [x] Implement heartbeat monitoring and timeout handling.
- [x] **Task: Implement `WorkerPool` Orchestrator** (e83fa4f)
    - [x] Dynamic scaling of worker processes.
    - [x] Logic for "Batch Stealing" or task distribution to persistent workers.
- [x] **Task: Write Tests for Worker Resilience** (eb22302)
    - [x] Test automatic restart after a simulated worker crash.
    - [x] Test graceful shutdown of the entire pool.
- [x] **Task: Conductor - User Manual Verification 'Persistent Worker Lifecycle' (Protocol in workflow.md)** (3239e0e)

## Phase 3: Hot Loop Rendering & State Management [checkpoint: 27c1bc7]
Integrating the persistent backend into the Blender/BlenderProc rendering logic.

- [x] **Task: Implement Backend "Warm-up" Logic** (c8eb926)
    - [x] Add `load_assets` command to persistent backend to pre-load HDRIs and textures.
    - [x] Implement VRAM monitoring hooks.
- [x] **Task: Implement "Partial Reset" in `blender_main.py`** (a8ba22a)
    - [x] Modify rendering loop to clear only volatile objects (tags, camera).
    - [x] Implement state validation using `StateHash`.
- [x] **Task: Hot Loop Integration Test** (93b4a0b)
    - [x] End-to-end test: Generate 10 images using a single persistent worker.
    - [x] Verify 3-5s startup cost is only incurred once.
- [x] **Task: Conductor - User Manual Verification 'Hot Loop Rendering & State Management' (Protocol in workflow.md)** (27c1bc7)

## Phase 4: Observability & Optimization [checkpoint: 41f71f1]
Adding telemetry and fine-tuning performance.

- [x] **Task: Implement VRAM Guardrails** (41afe76)
    - [x] Add logic to trigger a full worker restart if VRAM threshold is exceeded.
- [x] **Task: Structured Logging & Telemetry Dashboard** (d372a9b)
    - [x] Pipe ZMQ telemetry to Polars for throughput analysis.
- [x] **Task: Final Performance Benchmarking** (64dc037)
    - [x] Compare throughput (images/min) vs. the "Cold" baseline.
- [x] **Task: Conductor - User Manual Verification 'Observability & Optimization' (Protocol in workflow.md)** (41f71f1)
