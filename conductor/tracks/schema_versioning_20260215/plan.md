# Implementation Plan: Strict Schema Versioning

## Phase 1: Foundation - Schema Versioning & Migration Engine [checkpoint: 02122ee]
Isolate the migration logic and update the core models to support version metadata.

- [x] Task: Create `SchemaMigrator` utility (43b034f)
    - [x] Create `src/render_tag/core/migration.py`
    - [x] Implement `SchemaMigrator` class with support for sequential transformation functions.
    - [x] Define baseline migration for `0.0 -> 1.0` (adding the version field).
- [x] Task: Update `GenConfig` Schema (43b034f)
    - [x] Add `version: str = "1.0"` to `GenConfig` in `src/render_tag/core/config.py`.
    - [x] Update `GenConfig` validators to handle version strings.
- [x] Task: Update `JobSpec` Schema (2b70d8d)
    - [ ] Add `version: str = "1.0"` to `JobSpec` in `src/render_tag/core/schema/job.py`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Integration - Migration into Resolution Phase
Inject the migrator into the existing configuration loading sequence.

- [ ] Task: Implement TDD for YAML Migration
    - [ ] Create `tests/unit/core/test_migration_yaml.py`.
    - [ ] Write failing tests for loading unversioned YAML and getting a versioned `GenConfig`.
- [ ] Task: Integrate Migrator into `load_config`
    - [ ] Update `load_config` in `src/render_tag/core/config.py` to run the migrator before model validation.
- [ ] Task: Implement TDD for JobSpec Migration
    - [ ] Create `tests/unit/core/test_migration_jobspec.py`.
    - [ ] Write failing tests for loading unversioned `job_spec.json`.
- [ ] Task: Integrate Migrator into `JobSpec` deserialization
    - [ ] Update `JobSpec.model_validate_json` (or loading utility) to apply migrations.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Automation - On-Disk Upgrades & Validation
Enable the "Self-Healing" capability where legacy files are automatically upgraded on the filesystem.

- [ ] Task: Implement On-Disk Upgrade Logic
    - [ ] Add `upgrade_file_on_disk` utility to `src/render_tag/core/migration.py`.
    - [ ] Logic: If a file was migrated from `0.0`, write the new dictionary back to the source path.
- [ ] Task: Final Integration Test
    - [ ] Verify that running `render-tag generate` with a legacy config file results in a versioned config file on disk.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
