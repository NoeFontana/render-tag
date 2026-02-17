# Specification: Smart Resume Logic (Orchestration Layer)

## Overview
Implement "Smart Resume" capabilities by enabling the Orchestrator to validate existing output files against a JobSpec before assigning work. This prevents redundant rendering and ensures dataset integrity by detecting and cleaning up incomplete shards.

## Functional Requirements
- **Deterministic Sharding**: Update `JobSpec` to ensure a deterministic mapping between `shard_id` and `scene_indices` (e.g., Shard 0 always contains Scenes 0-99).
- **Shard Validation**:
    - Implement `ShardValidator` to verify the existence of `ground_truth_shard_{id}.csv` and `coco_labels_shard_{id}.json`.
    - Validate CSV row counts against the expected `scenes_per_shard`.
- **Aggressive Cleanup**: If a shard is detected as incomplete or invalid, automatically delete the associated files before the Orchestrator re-assigns the shard.
- **CLI Resumption**:
    - Add a `--resume-from <path>` flag to the `generate` command.
    - If provided, the CLI must load the JobSpec directly and filter the workload to only include missing or invalid shards.
- **Fail-Fast Error Handling**: The CLI must exit immediately with an error if the `--resume-from` path is invalid or if the JobSpec configuration does not match the current environment.

## Non-Functional Requirements
- **Performance**: Shard validation should be efficient enough to not introduce significant delay during the startup of large jobs.
- **Robustness**: File deletion must handle potential permission or locking issues gracefully (log warning and skip/retry).

## Acceptance Criteria
- [ ] `JobSpec` produces identical scene assignments across different runs with the same parameters.
- [ ] `ShardValidator` correctly identifies missing or incomplete CSV/JSON files.
- [ ] CLI with `--resume-from` skips all valid, completed shards.
- [ ] Incomplete shards are deleted and successfully re-rendered in the resumed session.
- [ ] Invalid resume paths trigger a clear error message and process exit.

## Out of Scope
- Resuming at the individual scene level within a shard (resumption is at the shard level).
- Automatic detection of interrupted jobs without the `--resume-from` flag.
