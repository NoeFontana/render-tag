# Track Specification: Decoupling the Execution Context (Inversion of Control)

## Overview
This track implements Phase 3 of the \"Decoupling the Execution Context\" initiative. It refactors the rendering orchestrator into a pure domain executor by extracting presentation logic, removing terminal-specific side-effects, and standardizing its output via a robust Data Transfer Object (DTO).

## Functional Requirements
1.  **OrchestrationResult DTO:**
    -   Implement `OrchestrationResult` as a **Pydantic Model** for strict validation and type safety.
    -   Must capture:
        -   Successful and failed scene counts.
        -   Detailed worker crash metrics and error logs.
        -   Serialized exception traces for debugging.
        -   **Execution Timing:** Total duration and per-stage timings.
        -   **Resource Utilization:** Worker-reported RAM and VRAM metrics.
        -   **Resumption Stats:** Count of scenes skipped by smart resumption.
        -   **Provenance Metadata:** SHA256 hashes of job specs and environment state.
2.  **Pure Orchestrator Logic:**
    -   Remove all dependencies on `typer`, `rich`, and `sys.exit` from `orchestrator.py`.
    -   Catch and package all terminal-level failures into the `OrchestrationResult` return object.
    -   Ensure the orchestrator is safe to run in headless environments (cloud functions, CI/CD).
3.  **CLI Reporter Strategy:**
    -   Extract all presentation logic into the CLI layer.
    -   Implement a **Plug-and-Play Reporters** strategy to allow different output formats (Rich Terminal, JSON, File).
    -   Centralize process control (e.g., `sys.exit(1)`) in the CLI entry points based on the returned result.

## Non-Functional Requirements
-   **Testability:** Orchestration should be verifiable using standard unit tests without mocking stdout or terminal state.
-   **Observability:** Standardized result objects must provide high-fidelity telemetry for downstream auditing.
-   **Isolation:** Strict separation between execution (Backend/Orchestration) and presentation (CLI).

## Acceptance Criteria
- [ ] `orchestrate()` function returns a valid `OrchestrationResult` pydantic model.
- [ ] `orchestrator.py` contains zero imports from `typer` or `rich`.
- [ ] The CLI generates identical (or improved) rich progress bars and error tables using the new reporter classes.
- [ ] Integration tests verify that a job failure in the orchestrator does not trigger an immediate `sys.exit`.
- [ ] Automated benchmarks verify that the timing and resource metrics are accurately reported.

## Out of Scope
-   Dynamic multi-process worker pool resizing (reserved for a later phase).
-   Web-based UI implementation for live monitoring.
-   Support for external (non-ZMQ) worker backends.
