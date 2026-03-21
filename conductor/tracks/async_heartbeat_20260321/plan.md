# Implementation Plan: Asynchronous Heartbeat Mechanism

## Phase 1: Immutable State Schema and Worker Thread
- [x] Task: Define the `WorkerSnapshot` Immutable Schema fb3eb4b
    - [ ] Create a frozen dataclass or Pydantic model for `WorkerSnapshot`.
    - [ ] Update `Telemetry` schema to support the new metrics (Object Count, CPU).
- [x] Task: Implement the Telemetry Emission Thread a449dee
    - [ ] Create `src/render_tag/backend/telemetry.py` containing the emission logic.
    - [ ] Implement the `poll_metrics()` function using `psutil` and Blender APIs.
    - [ ] Update `scripts/worker_bootstrap.py` to spawn the daemon thread.
- [ ] Task: Write Tests for Telemetry Emission
    - [ ] Verify that heartbeats are emitted at the correct interval.
    - [ ] Mock ZMQ PUB to ensure the payload format is correct.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Immutable State Schema and Worker Thread' (Protocol in workflow.md)

## Phase 2: Health Monitor and Ingestion Logic
- [ ] Task: Create the `HealthMonitor` Component
    - [ ] Implement `src/render_tag/orchestration/monitor.py`.
    - [ ] Design the lock-free `registry` using atomic dictionary updates.
- [ ] Task: Implement the ZMQ SUB Ingestion Loop
    - [ ] Create a background ingestion thread that updates the registry on $O(1)$ lookup.
    - [ ] Ensure the `SUB` socket correctly handles the multi-worker topic tagging.
- [ ] Task: Write Unit Tests for `HealthMonitor`
    - [ ] Verify thread-safe state ingestion under high frequency.
    - [ ] Test the lock-free read path.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Health Monitor and Ingestion Logic' (Protocol in workflow.md)

## Phase 3: Orchestrator Integration and Hot-Loop Decoupling
- [ ] Task: Decouple `UnifiedWorkerOrchestrator` from Network Health Checks
    - [ ] Inject `HealthMonitor` into `UnifiedWorkerOrchestrator`.
    - [ ] Refactor `_check_worker_health` to use the local registry.
    - [ ] Remove synchronous `CommandType.STATUS` calls from the critical path.
- [ ] Task: Write Integration Tests for Decoupled Hot Loop
    - [ ] Benchmark `_check_worker_health` latency.
    - [ ] Ensure workers are correctly released and returned to the queue based on local state.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Orchestrator Integration and Hot-Loop Decoupling' (Protocol in workflow.md)

## Phase 4: Watchdog Protocol and Persistence
- [ ] Task: Implement the Watchdog Sweep
    - [ ] Add a periodic sweep to `HealthMonitor` to flag `UNRESPONSIVE` workers.
    - [ ] Integrate with the orchestrator's reaper logic.
- [ ] Task: Implement Telemetry Persistence
    - [ ] Add NDJSON logging to the `HealthMonitor`.
    - [ ] Ensure logs are written to the job output directory.
- [ ] Task: Write Regression and Stress Tests
    - [ ] Simulate worker crashes and verify Watchdog detection.
    - [ ] Verify data integrity of `telemetry.ndjson`.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Watchdog Protocol and Persistence' (Protocol in workflow.md)
