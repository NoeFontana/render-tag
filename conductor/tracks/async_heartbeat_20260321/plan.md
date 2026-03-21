# Implementation Plan: Asynchronous Heartbeat Mechanism

## Phase 1: Immutable State Schema and Worker Thread [checkpoint: c05b263]
- [x] Task: Define the `WorkerSnapshot` Immutable Schema fb3eb4b
    - [ ] Create a frozen dataclass or Pydantic model for `WorkerSnapshot`.
    - [ ] Update `Telemetry` schema to support the new metrics (Object Count, CPU).
- [x] Task: Implement the Telemetry Emission Thread a449dee
    - [ ] Create `src/render_tag/backend/telemetry.py` containing the emission logic.
    - [ ] Implement the `poll_metrics()` function using `psutil` and Blender APIs.
    - [ ] Update `scripts/worker_bootstrap.py` to spawn the daemon thread.
- [x] Task: Write Tests for Telemetry Emission 0231672
    - [ ] Verify that heartbeats are emitted at the correct interval.
    - [ ] Mock ZMQ PUB to ensure the payload format is correct.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Immutable State Schema and Worker Thread' (Protocol in workflow.md) c05b263

## Phase 2: Health Monitor and Ingestion Logic [checkpoint: 9a11134]
- [x] Task: Create the `HealthMonitor` Component 4d4191c
    - [ ] Implement `src/render_tag/orchestration/monitor.py`.
    - [ ] Design the lock-free `registry` using atomic dictionary updates.
- [x] Task: Implement the ZMQ SUB Ingestion Loop 4d4191c
    - [ ] Create a background ingestion thread that updates the registry on $O(1)$ lookup.
    - [ ] Ensure the `SUB` socket correctly handles the multi-worker topic tagging.
- [x] Task: Write Unit Tests for `HealthMonitor` 9c4f4b9
    - [ ] Verify thread-safe state ingestion under high frequency.
    - [ ] Test the lock-free read path.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Health Monitor and Ingestion Logic' (Protocol in workflow.md) 9a11134

## Phase 3: Orchestrator Integration and Hot-Loop Decoupling [checkpoint: 4def28a]
- [x] Task: Decouple `UnifiedWorkerOrchestrator` from Network Health Checks d5ea916
    - [ ] Inject `HealthMonitor` into `UnifiedWorkerOrchestrator`.
    - [ ] Refactor `_check_worker_health` to use the local registry.
    - [ ] Remove synchronous `CommandType.STATUS` calls from the critical path.
- [x] Task: Write Integration Tests for Decoupled Hot Loop 0ced4cb
    - [ ] Benchmark `_check_worker_health` latency.
    - [ ] Ensure workers are correctly released and returned to the queue based on local state.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Orchestrator Integration and Hot-Loop Decoupling' (Protocol in workflow.md) 4def28a

## Phase 4: Watchdog Protocol and Persistence [checkpoint: b8edb97]
- [x] Task: Implement the Watchdog Sweep bf9e209
    - [ ] Add a periodic sweep to `HealthMonitor` to flag `UNRESPONSIVE` workers.
    - [ ] Integrate with the orchestrator's reaper logic.
- [x] Task: Implement Telemetry Persistence e417b10
    - [ ] Add NDJSON logging to the `HealthMonitor`.
    - [ ] Ensure logs are written to the job output directory.
- [x] Task: Write Regression and Stress Tests f7ae365
    - [ ] Simulate worker crashes and verify Watchdog detection.
    - [ ] Verify data integrity of `telemetry.ndjson`.
- [x] Task: Conductor - User Manual Verification 'Phase 4: Watchdog Protocol and Persistence' (Protocol in workflow.md) b8edb97

## Phase: Review Fixes
- [x] Task: Apply review suggestions a565254
