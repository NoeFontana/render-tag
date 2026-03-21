# Implementation Plan: Decoupling the Execution Context (Inversion of Control)

## Phase 1: Domain-Specific Result Object (DTO)
- [x] Task: Define the `OrchestrationResult` Pydantic Model e18d519
    - [ ] Create `src/render_tag/orchestration/result.py`.
    - [ ] Implement `OrchestrationResult` with fields for counts, metrics, timings, and metadata.
    - [ ] Add sub-models for `WorkerMetrics` and `ErrorRecord`.
- [x] Task: Write Tests for `OrchestrationResult` 5725596
    - [ ] Verify serialization/deserialization.
    - [ ] Ensure all required fields are correctly validated.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Domain-Specific Result Object (DTO)' (Protocol in workflow.md)

## Phase 2: Excise Presentation Logic from Orchestrator
- [ ] Task: Remove CLI Dependencies from `orchestrator.py`
    - [ ] Delete all imports of `typer`, `rich`, and `sys.exit`.
    - [ ] Replace `rich.progress` with a pure data-callback mechanism for progress reporting.
- [ ] Task: Refactor `orchestrate()` for Pure Execution
    - [ ] Update function signature to return `OrchestrationResult`.
    - [ ] Wrap main orchestration loop in a try-except to catch all terminal failures.
    - [ ] Package execution metadata (timing, resources) into the result object.
- [ ] Task: Write Unit Tests for Pure Orchestration
    - [ ] Mock the worker server and ZMQ layer.
    - [ ] Verify that `orchestrate()` returns a complete result object without process side-effects.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Excise Presentation Logic from Orchestrator' (Protocol in workflow.md)

## Phase 3: Push Side-Effects to the Outer Shell (CLI)
- [ ] Task: Implement Plug-and-Play Reporter Strategy
    - [ ] Create `src/render_tag/cli/reporters.py`.
    - [ ] Define a `BaseReporter` interface (Protocol).
    - [ ] Implement `RichTerminalReporter` using existing `rich` logic.
    - [ ] Implement `JsonFileReporter` for headless environments.
- [ ] Task: Refactor CLI Entry Points
    - [ ] Update `src/render_tag/cli/main.py` (or relevant commands) to invoke the orchestrator.
    - [ ] Pass a reporter instance to the orchestrator (or handle progress via callbacks).
    - [ ] Execute `sys.exit(1)` at the CLI layer only if the result indicates critical failure.
- [ ] Task: Write Integration Tests for CLI and Orchestrator
    - [ ] Verify that the CLI correctly presents results from a successful and failed run.
    - [ ] Ensure that a failed run returns a non-zero exit code to the shell.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Push Side-Effects to the Outer Shell (CLI)' (Protocol in workflow.md)

## Phase 4: Final Validation and Quality Gates
- [ ] Task: Verify End-to-End Metrics and Type Safety
    - [ ] Run a full generation job and verify the accuracy of the reported metrics.
    - [ ] Perform a final type check using `ty check` on the modified modules.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final Validation and Quality Gates' (Protocol in workflow.md)
