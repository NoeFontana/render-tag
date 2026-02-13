# Specification: Structured Observability Pipeline (JSON IPC)

## Overview
Replace the current brittle "printf debugging" and raw text scraping with a structured observability pipeline. This system converts the Blender backend into a telemetry producer emitting NDJSON (Newline Delimited JSON) over `stdout`, which the Orchestrator (Consumer) then ingests, routes, and visualizes.

## Goals
- Clean the terminal by isolating core Blender noise from project-specific logic.
- Provide structured telemetry for metrics (render time, VRAM), progress, and errors.
- Enable high-performance, non-blocking feedback during generation.
- Modernize the Backend-to-Host communication protocol.

## Functional Requirements
1.  **Telemetry Protocol (The "Wire Format")**:
    -   Format: NDJSON serialized with `orjson`.
    -   Mandatory Schema:
        ```json
        {
          "type": "log" | "metric" | "progress" | "error",
          "level": "INFO" | "DEBUG" | "WARNING" | "ERROR",
          "logger": "string",
          "timestamp": "ISO8601",
          "message": "string",
          "payload": { ... } // Contextual structured data
        }
        ```
2.  **Backend Implementation (Producer)**:
    -   **Structured Formatter**: Implement `JSONFormatter` in `src/render_tag/common/logging.py`.
    -   **Bootstrap Hook**: Update `src/render_tag/backend/bootstrap.py` to configure the root logger with a `StreamHandler(sys.stdout)` using the `JSONFormatter`.
    -   **Stderr Redirection**: Redirect `sys.stderr` into the structured logger to capture unhandled Python exceptions as JSON errors.
    -   **Type Handling**: Ensure `mathutils.Vector/Matrix`, `Path`, and `numpy` types are serialized to primitives.
3.  **Orchestrator Implementation (Consumer)**:
    -   **Refactor Executor**: Update `run_blender_process` in `src/render_tag/orchestration/executors.py` to use `subprocess.PIPE`.
    -   **Log Router**: Implement a processing loop that:
        -   Parses JSON lines.
        -   Routes progress events to a `tqdm` progress bar.
        -   Redirects non-matching "Raw Blender Noise" to a `blender_raw.log` file in the output directory.
        -   Re-emits structured logs via the Orchestrator's internal logging system.
4.  **Telemetry Capture**:
    -   Prioritize capturing: Render time per frame, Peak VRAM, Tag visibility %, and Asset pool hits/misses.

## Non-Functional Requirements
- **Performance**: Use `orjson` to minimize overhead in the rendering loop.
- **Reliability**: The parser must be robust to malformed lines (e.g., partial JSON if Blender crashes).
- **Maintainability**: Centralize the logging configuration in the `common` module.

## Acceptance Criteria
- [ ] `JSONFormatter` implemented and tested with complex types (`Vector`, `Path`).
- [ ] Blender backend emits valid NDJSON logs when initialized.
- [ ] Orchestrator correctly drives a `tqdm` bar based on JSON progress events.
- [ ] Core Blender noise is no longer visible in the main terminal, but captured in `blender_raw.log`.
- [ ] Unhandled backend exceptions appear as structured errors in the Orchestrator log.

## Out of Scope
- Implementing a full-blown ELK stack or external metrics database.
- Capturing non-text output from Blender (like separate UI threads).
