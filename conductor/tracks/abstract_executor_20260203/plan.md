# Implementation Plan - Abstracting the Render Executor

This plan refactors the render execution logic into a pluggable interface to support local, containerized, and future cloud-based rendering.

## Phase 1: Infrastructure Foundations [checkpoint: 8343047]
**Goal:** Define the interface and implement the core abstraction.

- [x] Task: Define `RenderExecutor` Protocol 6e8d864
    - [ ] Create `src/render_tag/orchestration/executors.py`.
    - [ ] Define the `RenderExecutor` typing protocol.
    - [ ] Create an `ExecutorFactory` to instantiate the correct implementation based on a string name.
- [x] Task: Implement `LocalExecutor` f7cde3b
    - [ ] Migrate the current `subprocess.run` logic from `src/render_tag/cli.py` to the `LocalExecutor` class.
- [x] Task: Implement `MockExecutor` f7cde3b
    - [ ] Create a `MockExecutor` that simply logs the execution command and returns success.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure Foundations' (Protocol in workflow.md)

## Phase 2: CLI ## Phase 2: CLI & Orchestration Update Orchestration Update [checkpoint: 100c6c0]
**Goal:** Integrate the new executor system into the main pipeline.

- [x] Task: Update `render-tag generate` Command 4f69372
    - [ ] Add the `--executor` flag to the Typer command.
    - [ ] Refactor the `generate` function to use the `ExecutorFactory` instead of hardcoded subprocess calls.
- [x] Task: Update `run_local_parallel` 4f69372
    - [ ] Ensure that sharded parallel runs also respect the chosen executor.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI & Orchestration Update' (Protocol in workflow.md)

## Phase 3: Docker Implementation
**Goal:** Enable containerized rendering.

- [ ] Task: Implement `DockerExecutor`
    - [ ] Add `DockerExecutor` class to `executors.py`.
    - [ ] Implement volume mapping logic (mounting `output` directory).
    - [ ] Construct the `docker run` command using the pre-built image.
- [ ] Task: Integration Test - Docker Execution
    - [ ] Add a test case that attempts to run with the `mock` executor and verifies the flow. (Full Docker testing may be skipped if environment lacks Docker daemon).
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Docker Implementation' (Protocol in workflow.md)

## Phase 4: Verification & Documentation
**Goal:** Ensure full system integrity and user awareness.

- [ ] Task: Run Full Test Suite
    - [ ] Verify that reorganization didn't break existing local rendering.
- [ ] Task: Document Executor Usage
    - [ ] Update `README.md` or CLI help text with examples of how to use different executors.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Verification & Documentation' (Protocol in workflow.md)
