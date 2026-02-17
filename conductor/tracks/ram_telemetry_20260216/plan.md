# Plan: RAM Telemetry & Auto-Tuning

## Phase 1: Schema Updates
- [x] Task: Update `JobInfrastructure` for memory limits (d7831c3)
    - [x] Write failing test in `tests/unit/core/test_schema_memory.py` to verify `max_memory_mb` field.
    - [x] Implement `max_memory_mb: int | None = None` in `src/render_tag/core/schema/job.py`.
    - [x] Verify tests pass.

## Phase 2: Dynamic Allocation (Orchestrator)
- [x] Task: Implement `calculate_worker_budget` (790f973)
    - [x] Write failing tests in `tests/unit/orchestration/test_resource_calc.py`.
    - [x] Create `src/render_tag/orchestration/resources.py` (or update `orchestrator.py`) with budget calculation logic.
    - [x] Implement auto-tuning: `(total_ram * 0.75) / num_workers`.
    - [x] Verify tests pass.
- [x] Task: Inject limit into worker launch (790f973)
    - [x] Update `PersistentWorkerProcess` in `src/render_tag/orchestration/worker.py` to accept `memory_limit_mb`.
    - [x] Update `UnifiedWorkerOrchestrator` to pass calculated limit.
    - [x] Verify via mock tests.

## Phase 3: Worker Sentinel (Enforcement)
- [x] Task: Implement memory monitoring in worker (53d82cf)
    - [x] Update `ZmqBackendServer` in `src/render_tag/backend/worker_server.py` to track memory usage.
    - [x] Implement periodic check in management loop.
    - [x] Implement `WorkerStatus.RESOURCE_LIMIT_EXCEEDED` logic.
    - [x] Add `gc.collect()` before final measurement.
    - [x] Verify with simulated leak tests.
- [x] Task: Update worker entrypoint (53d82cf)
    - [x] Update `src/render_tag/backend/zmq_server.py` to parse `--memory-limit-mb`.
    - [x] Pass limit to `ZmqBackendServer`.

## Phase 4: Resilient Recovery
- [x] Task: Implement Maintenance Restarts (53d82cf)
    - [x] Update `UnifiedWorkerOrchestrator.release_worker` logic to detect resource-limit exits.
    - [x] Ensure `retry_count` is NOT incremented for these specific exits.
    - [x] Verify automatic replacement spawning.
    - [x] Verify integration with integration tests.
