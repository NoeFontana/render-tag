# Implementation Plan: Decoupling the Execution Context (Inversion of Control)

## Phase 1: Domain-Specific Result Object (DTO) [checkpoint: 61567ca]
- [x] Task: Define the `OrchestrationResult` Pydantic Model e18d519
    - [ ] Create `src/render_tag/orchestration/result.py`.
    - [ ] Implement `OrchestrationResult` with fields for counts, metrics, timings, and metadata.
    - [ ] Add sub-models for `WorkerMetrics` and `ErrorRecord`.
- [x] Task: Write Tests for `OrchestrationResult` 5725596
    - [ ] Verify serialization/deserialization.
    - [ ] Ensure all required fields are correctly validated.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Domain-Specific Result Object (DTO)' (Protocol in workflow.md) 61567ca

## Phase 2: Excise Presentation Logic from Orchestrator [checkpoint: 10c04af]
- [x] Task: Remove CLI Dependencies from `orchestrator.py` fbc1c2e
    - [x] Delete all imports of `typer`, `rich`, and `sys.exit`.
    - [x] Replace `rich.progress` with a pure data-callback mechanism for progress reporting.
- [x] Task: Refactor `orchestrate()` for Pure Execution fbc1c2e
    - [x] Update function signature to return `OrchestrationResult`.
    - [x] Wrap main orchestration loop in a try-except to catch all terminal failures.
    - [x] Package execution metadata (timing, resources) into the result object.
- [x] Task: Write Unit Tests for Pure Orchestration fbc1c2e
    - [x] Mock the worker server and ZMQ layer.
    - [x] Verify that `orchestrate()` returns a complete result object without process side-effects.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Excise Presentation Logic from Orchestrator' (Protocol in workflow.md) 10c04af

## Phase 3: Push Side-Effects to the Outer Shell (CLI) [checkpoint: 4f3dc30]
- [x] Task: Implement Plug-and-Play Reporter Strategy ea1567e
    - [x] Create `src/render_tag/cli/reporters.py`.
    - [x] Define a `BaseReporter` interface (Protocol).
    - [x] Implement `RichTerminalReporter` using existing `rich` logic.
    - [x] Implement `JsonFileReporter` for headless environments.
- [x] Task: Refactor CLI Entry Points df740c8
    - [x] Update `src/render_tag/cli/main.py` (or relevant commands) to invoke the orchestrator.
    - [x] Pass a reporter instance to the orchestrator (or handle progress via callbacks).
    - [x] Execute `sys.exit(1)` at the CLI layer only if the result indicates critical failure.
- [x] Task: Write Integration Tests for CLI and Orchestrator df740c8
    - [x] Verify that the CLI correctly presents results from a successful and failed run.
    - [ ] Ensure that a failed run returns a non-zero exit code to the shell.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Push Side-Effects to the Outer Shell (CLI)' (Protocol in workflow.md) 4f3dc30

## Phase 4: Final Validation and Quality Gates [checkpoint: 4f3dc30]
- [x] Task: Verify End-to-End Metrics and Type Safety 4f3dc30
    - [x] Run a full generation job and verify the accuracy of the reported metrics.
    - [x] Perform a final type check using `ty check` on the modified modules.
- [x] Task: Conductor - User Manual Verification 'Phase 4: Final Validation and Quality Gates' (Protocol in workflow.md) 4f3dc30

## Phase: Review Fixes
- [x] Task: Apply review suggestions eead535
