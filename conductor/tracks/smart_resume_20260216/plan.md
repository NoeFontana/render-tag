# Plan: Smart Resume Logic (Orchestration Layer)

## Phase 1: Deterministic Sharding & Validation Logic
- [x] Task: Update `JobSpec` for Deterministic Mapping (6d38206)
    - [x] Write failing test in `tests/unit/core/test_job_spec_determinism.py` to verify `shard_id` to `scene_indices` mapping is consistent.
    - [x] Implement mapping logic in `src/render_tag/core/schema/job.py`.
    - [x] Verify tests pass.
- [ ] Task: Implement `ShardValidator`
    - [ ] Write failing tests in `tests/unit/orchestration/test_validator.py` for missing, incomplete, and valid shards.
    - [ ] Create `src/render_tag/orchestration/validator.py` with `ShardValidator` class.
    - [ ] Implement `validate_shard` logic (CSV row count, JSON existence).
    - [ ] Implement `aggressive_cleanup` logic to delete invalid shard files.
    - [ ] Verify tests pass.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Deterministic Sharding & Validation Logic' (Protocol in workflow.md)

## Phase 2: CLI Integration & Resumption Flow
- [ ] Task: Update CLI `generate` Command for Resumption
    - [ ] Write failing integration test in `tests/integration/test_resumption_cli.py`.
    - [ ] Add `--resume-from` argument to `src/render_tag/cli/generate.py`.
    - [ ] Implement JobSpec loading and ShardValidator invocation in CLI.
    - [ ] Implement workload filtering to only pass missing/invalid shards to the Orchestrator.
    - [ ] Add fail-fast validation for invalid paths or config mismatches.
    - [ ] Verify tests pass.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration & Resumption Flow' (Protocol in workflow.md)
