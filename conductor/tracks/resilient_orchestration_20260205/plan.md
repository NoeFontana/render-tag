# Implementation Plan - Resilient Orchestration & Fault Tolerance

This plan refactors the parallel execution layer to handle crashes, implement scene-level resuming, and balance worker load dynamically.

## Phase 1: Robust Worker Lifecycle & Signal Handling
**Goal:** Ensure child processes are managed safely and the orchestrator can detect and report crashes.

- [x] Task: Implement Signal Propagation
    - [x] Update `sharding.py` to handle `SIGINT`/`SIGTERM`.
    - [x] Ensure all spawned Blender processes are terminated on orchestrator exit.
- [x] Task: Enhance Worker Monitoring
    - [x] Refactor `run_local_parallel` to capture and analyze return codes of subprocesses.
    - [x] Log specific error messages for crashes (SEGFAULT, OOM, etc.).
- [x] Task: Conductor - User Manual Verification 'Phase 1: Worker Lifecycle' (Protocol in workflow.md)

## Phase 2: Checkpointing & Resume Logic
**Goal:** Enable the system to recover from failures without redundant work.

- [ ] Task: Implement Sidecar-Based Completion Check
    - [ ] Create a utility in `orchestration/sharding.py` to identify completed scenes by scanning for sidecar JSONs.
- [ ] Task: Add `--resume` Flag to CLI
    - [ ] Update `generate` command in `cli.py` to support the flag.
    - [ ] Pass the list of completed scene IDs to the `Generator` to exclude them from recipe creation.
- [ ] Task: Integration Test - Crash Recovery
    - [ ] Create a test that kills a worker midway and verifies that a subsequent `--resume` run finishes the job correctly.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Checkpointing' (Protocol in workflow.md)

## Phase 3: Dynamic Load Balancing (Batch Stealing)
**Goal:** Optimize throughput by moving from static ranges to dynamic task distribution.

- [ ] Task: Implement Task Batching Engine
    - [ ] Refactor the orchestration loop to divide the total scene count into smaller batches (e.g., 10 scenes).
    - [ ] Workers pull batches from a synchronized task pool.
- [ ] Task: Resource Telemetry (Optional/Stretch)
    - [ ] Implement a basic `ResourceMonitor` that logs system RAM/VRAM usage.
- [ ] Task: Benchmarking - Static vs. Dynamic
    - [ ] Compare throughput between the old static sharding and the new dynamic model using variable-complexity scenes.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Dynamic Distribution' (Protocol in workflow.md)

## Phase 4: Final Verification & Reliability Testing
**Goal:** Ensure 100% data integrity and system stability.

- [ ] Task: Run Stress Tests
    - [ ] Execute a 1,000-scene run with intentional "chaos" (randomly killing workers).
    - [ ] Verify that final CSV/COCO merge is consistent and has no duplicates.
- [ ] Task: Run Full Test Suite
    - [ ] Ensure no regressions in existing camera or shader logic.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final Integration' (Protocol in workflow.md)
