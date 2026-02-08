# Specification: Immutable Job Spec (The Contract)

## Overview
Currently, rendering jobs are defined by transient command-line flags and local environment states. This creates a "reproducibility gap" when moving from local development to cloud-scale orchestration. This track introduces a rigid, immutable JSON schema (the "Job Spec") that acts as a self-contained unit of work, ensuring pixel-perfect reproducibility and auditability.

## Goals
- **Eliminate Environment Drift**: Lock the exact environment and engine versions.
- **Hermetic Execution**: Decouple "Planning" from "Execution" via a lockfile.
- **Provable Data**: Attach cryptographically verifiable provenance to every generated dataset.

## Functional Requirements
- **Immutable Schema**:
    - Defined as a frozen Pydantic V2 model in `src/render_tag/schema/job.py`.
    - Content-addressed: The `job_id` is the SHA256 hash of the job definition.
- **Contract Details**:
    - **Environment**: SHA256 of `uv.lock` and explicit Blender version string.
    - **Assets**: Content-addressable Asset Lock Hash (from the Asset Manager).
    - **Logic**: SHA256 of the source configuration and Generator code version.
    - **Workload**: Deterministic seed, shard index, and shard size.
- **CLI Integration**:
    - `render-tag lock`: Generates the `job.json` from a YAML config and current environment state.
    - `render-tag run --job job.json`: Executes a job strictly according to the lockfile.
- **Verification**:
    - Output a `manifest.json` in the results directory containing the Job ID and output file hashes.

## Non-Functional Requirements
- **Immutability**: Once a `job.json` is generated, any change to its content must result in a new `job_id`.
- **Performance**: Schema validation and Job ID generation must add negligible overhead to the initialization phase.

## Acceptance Criteria
- [ ] A `job.json` can be generated locally and executed in a different environment (e.g., Docker) with identical results.
- [ ] The `job.json` fails validation if the `uv.lock` on the executor does not match the spec.
- [ ] A `render-tag verify-output` command can confirm that a dataset matches its originating `job.json`.

## Out of Scope
- Automatic deployment to cloud providers (this track only handles the *contract*).
- Real-time monitoring of job execution.
