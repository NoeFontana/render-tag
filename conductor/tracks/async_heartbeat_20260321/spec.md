# Track Specification: Asynchronous Heartbeat Mechanism

## Overview
This track refactors the rendering system's health monitoring from a synchronous Request-Reply (REQ/REP) pattern to an asynchronous Publish-Subscribe (PUB/SUB) topology. By decoupling telemetry (control plane) from rendering tasks (data plane), we eliminate pipeline stalls and priority inversion in the orchestrator's allocation loop.

## Functional Requirements
1.  **Telemetry Emission (Worker Side):**
    -   Spawn a dedicated daemon thread in `worker_bootstrap.py` for health reporting.
    -   Establish a ZMQ PUB socket on `base_port + 1000` (offset by worker ID).
    -   Periodically (every 1000ms) publish an immutable `WorkerSnapshot` containing:
        -   RAM/VRAM utilization.
        -   CPU Usage.
        -   Active Scene ID.
        -   Blender Object Count.
2.  **Telemetry Ingestion (Orchestrator Side):**
    -   Implement a `HealthMonitor` daemon running in a background thread.
    -   Maintain a thread-safe, lock-free `registry` mapping `worker_id` to the latest `WorkerSnapshot`.
    -   Use atomic reference swapping for $O(1)$ state updates.
3.  **Decoupled Health Check:**
    -   Refactor `UnifiedWorkerOrchestrator._check_worker_health` to perform local dictionary lookups against the monitor's registry instead of network REQ calls.
    -   Enforce liveness checks via a `Watchdog` sweep that flags workers as `UNRESPONSIVE` after 10 seconds of heartbeat silence.
4.  **Observability:**
    -   Persist all received telemetry records to an NDJSON file (`telemetry.ndjson`) in the job's output directory for post-mortem analysis.

## Non-Functional Requirements
-   **Zero-Latency Reads:** The orchestrator's critical path must never block on I/O or mutex contention when checking health.
-   **Thread Safety:** Utilize immutable data structures to prevent race conditions during state interrogation.
-   **Resource Efficiency:** The telemetry thread must have negligible impact on Blender's rendering performance.

## Acceptance Criteria
- [ ] Worker emits heartbeats at a strict 1000ms interval.
- [ ] Orchestrator detects catastrophic worker failure within 10s of heartbeat loss.
- [ ] `_check_worker_health` execution time is < 1ms.
- [ ] `telemetry.ndjson` contains a complete time-series of metrics for every active worker.

## Out of Scope
-   Automated scaling of the worker pool based on telemetry metrics.
-   Integration with external monitoring platforms (e.g., Prometheus, Grafana).
-   Web-based live-monitoring dashboard.
