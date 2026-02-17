# Specification: RAM Telemetry & Auto-Tuning

## Overview
Implement dynamic resource allocation and memory telemetry to ensure stable rendering across varying hardware profiles. The system will automatically calculate safe memory budgets per worker and perform preventative restarts if a worker exceeds its allocated budget, preventing system instability or swapping.

## Functional Requirements
- **Flexible Memory Contract**:
    - Update `JobInfrastructure` schema to support an optional `max_memory_mb` field.
    - If `max_memory_mb` is `None`, the system defaults to "Auto-Tuning" mode.
- **Dynamic Orchestrator Allocation**:
    - Implement logic to calculate memory budget per worker during job initialization.
    - **Auto-Tuning Logic**: `(System Total RAM * 0.75) / Number of Workers`.
    - Inject the calculated or explicit limit into workers via the `--memory-limit-mb` CLI flag.
- **Worker Sentinel (Enforcement)**:
    - Update the worker backend (`zmq_server.py`) to parse and respect the memory limit.
    - Implement a monitoring check triggered by:
        - **Post-GC**: Explicitly run `gc.collect()` before measuring memory usage to ensure accurate metrics.
        - **Heartbeat**: Perform periodic checks within the management thread during active rendering.
    - If usage exceeds the limit, the worker must transition to `WorkerStatus.RESOURCE_LIMIT_EXCEEDED` and perform a clean exit (`sys.exit(0)`).
- **Resilient Recovery**:
    - The Orchestrator must detect `RESOURCE_LIMIT_EXCEEDED` exits as "Maintenance Restarts" rather than failures.
    - Maintenance restarts should not increment the job's failure/retry counter.
    - The Orchestrator must immediately spawn a replacement worker to resume the interrupted shard.

## Non-Functional Requirements
- **Accuracy**: Use `psutil` for precise RSS (Resident Set Size) measurement.
- **Performance**: Garbage collection and memory checks should introduce negligible overhead compared to the rendering task.
- **Transparency**: Log all memory-driven restarts with "current usage vs. limit" context for auditability.

## Acceptance Criteria
- [ ] `JobSpec` accepts and serializes `max_memory_mb` (integer or null).
- [ ] Orchestrator correctly calculates a 6GB budget on a 32GB system with 4 workers (32 * 0.75 / 4).
- [ ] A worker process successfully shuts down and returns `RESOURCE_LIMIT_EXCEEDED` when forced past its limit.
- [ ] The Orchestrator restarts a memory-exceeded worker without counting it as a "Failed attempt".
- [ ] Total system memory usage remains stable (no swap triggers) during a high-worker-count generation job.

## Out of Scope
- Dynamic adjustment of memory limits *during* a running job (limits are set at startup).
- VRAM (GPU memory) auto-tuning (this phase focuses strictly on System RAM).
