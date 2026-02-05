# Specification - Infrastructure: Resilient Orchestration & Fault Tolerance

## Overview
As the project scales to high-volume generation (10,000+ scenes), the current static sharding and lack of fault tolerance become major bottlenecks. A single Blender crash currently fails the entire session. This track refactors the orchestration layer to manage worker health, implement scene-level resuming via sidecar verification, and utilize a "Batch Stealing" model for dynamic load balancing.

## Functional Requirements
- **Fault-Tolerant Orchestrator:**
    - Monitor worker exit codes.
    - Implement automatic retries for crashed processes.
    - Gracefully handle `SIGTERM`/`SIGINT` to ensure all children are reaped and final data is flushed.
- **Scene-Level Checkpointing & Resume:**
    - Use existing `sidecar.json` files to verify scene completion.
    - Add a `--resume` flag to the `generate` command.
    - Skip already-completed scenes at the start of a new run or after a crash.
- **Dynamic Load Balancing (Batch Stealing):**
    - Refactor `run_local_parallel` to use a task-batching model (default batch size = 10).
    - Workers pull the next batch of scenes upon completion of the current set.
- **Resource Monitoring:**
    - Basic telemetry for RAM, VRAM (via `nvidia-smi` or similar if available), and execution time.
    - Pause task distribution if system memory pressure is critical.

## Non-Functional Requirements
- **Reliability:** 100% data integrity after a crash (no partial CSVs or corrupted COCO files).
- **Scalability:** Support horizontal scaling to 32+ parallel workers without significant overhead.
- **Observability:** Log clear errors when a worker fails, including the specific scene ID and crash type.

## Acceptance Criteria
- [ ] A run with `--resume` correctly skips existing scenes verified by sidecars.
- [ ] Forcing a crash (e.g., `kill -9` on a Blender child) results in the orchestrator relaunching the worker and finishing the run.
- [ ] Generation throughput is balanced across workers even with variable scene complexity.
- [ ] Interrupting the run with `Ctrl+C` reaps all child processes instantly.
