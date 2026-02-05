# Implementation Plan - Principal-Level Asset Management

This plan implements a robust asset management system using Hugging Face as the remote SSoT, ensuring hermetic reproducibility.

## Phase 1: Core Logic & AssetManager Interface
**Goal:** Implement the bidirectional sync engine and directory enforcement.

- [x] Task: Implement `AssetManager` Class 0835391
    - [ ] Create `src/render_tag/orchestration/assets.py`.
    - [ ] Integrate `huggingface_hub` for `snapshot_download` and `upload_folder`.
    - [ ] Implement local directory contract enforcement (creating subfolders).
- [x] Task: Unit Tests for Sync Logic 0835391
    - [ ] Mock Hugging Face API calls.
    - [ ] Verify that the manager correctly identifies missing or changed files.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Core Logic' (Protocol in workflow.md)

## Phase 2: CLI Integration
**Goal:** Expose asset management via the CLI.

- [ ] Task: Create `assets` Command Group
    - [ ] Update `src/render_tag/cli.py` to add `assets` subcommand.
    - [ ] Implement `pull` command using `AssetManager.pull()`.
    - [ ] Implement `push` command with `--force` and authentication checks.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration' (Protocol in workflow.md)

## Phase 3: Runtime Safety & Pre-Flight Checks
**Goal:** Integrate asset verification into the generation pipeline.

- [ ] Task: Implement Pre-Flight Check
    - [ ] Create an `AssetValidator` utility.
    - [ ] Update `generate` command to call validator before rendering.
- [ ] Task: Add Interactive Prompt
    - [ ] Implement logic to detect TTY and prompt for download if assets are missing.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Runtime Safety' (Protocol in workflow.md)

## Phase 4: Final Verification & Documentation
**Goal:** Ensure zero-config onboarding and full system integrity.

- [ ] Task: Run Full Test Suite
    - [ ] Verify that no regressions were introduced in existing rendering paths.
- [ ] Task: Update Onboarding Guide
    - [ ] Add `render-tag assets pull` instructions to the `README.md`.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final Verification' (Protocol in workflow.md)
