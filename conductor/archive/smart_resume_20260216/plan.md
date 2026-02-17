# Plan: Smart Resume Logic (Orchestration Layer)

## Phase 1: Deterministic Sharding & Validation Logic [checkpoint: f3fae6a]
- [x] Task: Update `JobSpec` for Deterministic Mapping (6d38206)
    - [x] Write failing test in `tests/unit/core/test_job_spec_determinism.py` to verify `shard_id` to `scene_indices` mapping is consistent.
    - [x] Implement mapping logic in `src/render_tag/core/schema/job.py`.
    - [x] Verify tests pass.
- [x] Task: Implement `ShardValidator` (b889aba)
    - [x] Write failing tests in `tests/unit/orchestration/test_validator.py` for missing, incomplete, and valid shards.
    - [x] Create `src/render_tag/orchestration/validator.py` with `ShardValidator` class.
    - [x] Implement `validate_shard` logic (CSV row count, JSON existence).
    - [x] Implement `aggressive_cleanup` logic to delete invalid shard files.
    - [x] Verify tests pass.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Deterministic Sharding & Validation Logic' (Protocol in workflow.md)

## Phase 2: CLI Integration & Resumption Flow [checkpoint: e2b4768]
- [x] Task: Update CLI `generate` Command for Resumption (0a4d0c6)
    - [x] Write failing integration test in `tests/integration/test_resumption_cli.py`.
    - [x] Add `--resume-from` argument to `src/render_tag/cli/generate.py`.
    - [x] Implement JobSpec loading and ShardValidator invocation in CLI.
    - [x] Implement workload filtering to only pass missing/invalid shards to the Orchestrator.
    - [x] Add fail-fast validation for invalid paths or config mismatches.
    - [x] Verify tests pass.
- [x] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration & Resumption Flow' (Protocol in workflow.md)

## Phase: Review Fixes
- [x] Task: Apply review suggestions (32b85d1)
