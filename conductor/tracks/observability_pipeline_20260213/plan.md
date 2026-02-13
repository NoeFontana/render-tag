# Implementation Plan: Structured Observability Pipeline (JSON IPC)

Implement a high-performance, structured logging and telemetry pipeline between the Blender backend and the orchestrator using NDJSON and `orjson`.

## Phase 1: Common Infrastructure & Schema
- [x] Task: Install `orjson` and update `pyproject.toml`. 3e7a30d
- [x] Task: Implement `JSONFormatter` in `src/render_tag/common/logging.py`. 3e7a30d
    - [x] Add support for `mathutils`, `Path`, and `numpy` serialization.
    - [x] Define the base `LogSchema` using Pydantic or a typed dictionary.
- [x] Task: Write unit tests for `JSONFormatter` verifying serialization of complex types. 3e7a30d
- [x] Task: Conductor - User Manual Verification 'Phase 1: Common Infrastructure & Schema' (Protocol in workflow.md) 3e7a30d

## Phase 2: Backend Producer Implementation
- [x] Task: Update `src/render_tag/backend/bootstrap.py` to include `configure_logging()`. 1f98718
    - [x] Redirect root logger to `sys.stdout` with `JSONFormatter`.
    - [x] Redirect `sys.stderr` to the root logger.
- [x] Task: Add telemetry hooks to `src/render_tag/backend/render_loop.py` (Render time, VRAM). 1f98718
- [x] Task: Verify that running a script via `blender --python` emits valid JSON to stdout. 1f98718
- [x] Task: Conductor - User Manual Verification 'Phase 2: Backend Producer Implementation' (Protocol in workflow.md) 1f98718

## Phase 3: Orchestrator Consumer Implementation
- [x] Task: Refactor `run_blender_process` in `src/render_tag/orchestration/executors.py` to ingest piped output. f48a135
- [x] Task: Implement the "Log Router" logic. f48a135
    - [x] Parse NDJSON lines using `orjson`.
    - [x] Route `type: progress` to a `tqdm` instance.
    - [x] Redirect "Noise" to `blender_raw.log`.
- [x] Task: Implement graceful handling of backend crashes/partial JSON lines. f48a135
- [x] Task: Conductor - User Manual Verification 'Phase 3: Orchestrator Consumer Implementation' (Protocol in workflow.md) f48a135

## Phase 4: Finalization & Verification
- [x] Task: Run a full generation batch and verify `tqdm` progress and clean terminal output. f48a135
- [x] Task: Verify that `blender_raw.log` contains expected Blender background noise. f48a135
- [x] Task: Conductor - User Manual Verification 'Phase 4: Finalization & Verification' (Protocol in workflow.md) f48a135
