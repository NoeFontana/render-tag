# Implementation Plan: Immutable Job Spec

## Phase 1: Core Schema & Identity [checkpoint: 45c45c1]
- [x] Task: Define Immutable Job Schema (9ae5f16)
    - [x] Write failing unit tests for `JobSpec` validation and immutability (TDD)
    - [x] Implement `JobSpec` as a frozen Pydantic V2 model in `src/render_tag/schema/job.py`
    - [x] Implement `calculate_job_id()` to return SHA256 hash of the JSON-serialized spec
- [x] Task: Environment & Asset Fingerprinting (5fd9fd8)
    - [x] Write tests for lockfile hashing and version detection
    - [x] Implement `get_env_fingerprint()` (hashes `uv.lock`, detects Blender version)
    - [x] Integrate with existing `AssetManager` to pull the current `assets.lock` hash
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Schema & Identity' (Protocol in workflow.md)

## Phase 2: CLI Command - `render-tag lock` [checkpoint: a66bb43]
- [x] Task: Implement `lock` Command (0203e35)
    - [x] Write integration tests for `render-tag lock` CLI behavior
    - [x] Create `lock` command in `src/render_tag/cli/` to generate `job.json`
    - [x] Ensure `job.json` contains full context (Env, Assets, Config, Shard)
- [x] Task: Conductor - User Manual Verification 'Phase 2: CLI Command - lock' (Protocol in workflow.md)

## Phase 3: Job-Driven Execution Engine
- [ ] Task: Update Execution Logic
    - [ ] Write failing tests for job-based execution and environment validation
    - [ ] Extend `render-tag run` (or similar) to accept a `--job` path
    - [ ] Implement pre-execution guard: Fail if current `uv.lock` hash != `job.json` hash
- [ ] Task: Config Override Logic
    - [ ] Ensure CLI flags are ignored or validated against the `job.json` when running in job mode
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Job-Driven Execution Engine' (Protocol in workflow.md)

## Phase 4: Provenance & Verification
- [ ] Task: Automatic Manifest Generation
    - [ ] Write tests for post-render manifest creation
    - [ ] Implement `manifest.json` output in the results directory (links Output Files -> Job ID)
- [ ] Task: Verification Utility
    - [ ] Write tests for `render-tag verify-output`
    - [ ] Implement `verify-output` command to check file integrity and job provenance
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Provenance & Verification' (Protocol in workflow.md)