# Implementation Plan: Hugging Face Asset Migration

## Phase 1: Infrastructure and HF Integration
- [x] Task: Add `huggingface_hub` dependency and update environment [784528b]
    - [ ] Add `huggingface-hub` to `pyproject.toml`
    - [ ] Verify installation and accessibility in the environment
- [ ] Task: Create `AssetProvider` abstraction
    - [ ] Write failing tests for `AssetProvider` to handle local check and remote fetch
    - [ ] Implement `AssetProvider` in `src/render_tag/data_io/assets.py` using `huggingface_hub`
    - [ ] Verify tests pass and achieve >80% coverage
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure and HF Integration' (Protocol in workflow.md)

## Phase 2: CLI Sync Command Implementation
- [ ] Task: Implement `assets sync` CLI command
    - [ ] Write failing integration tests for `render-tag assets sync`
    - [ ] Add `assets` group and `sync` command to `src/render_tag/cli/main.py`
    - [ ] Implement full dataset download logic in the sync command
    - [ ] Verify tests pass and achieve >80% coverage
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Sync Command Implementation' (Protocol in workflow.md)

## Phase 3: On-Demand Downloading and Generator Integration
- [ ] Task: Integrate `AssetProvider` into `Generator`
    - [ ] Write failing tests for `Generator` attempting to use a missing asset
    - [ ] Modify `Generator` to use `AssetProvider` for resolving paths to tags, models, and textures
    - [ ] Ensure automatic download triggers if the file is missing locally
    - [ ] Verify tests pass and achieve >80% coverage
- [ ] Task: Conductor - User Manual Verification 'Phase 3: On-Demand Downloading and Generator Integration' (Protocol in workflow.md)

## Phase 4: Migration and Repository Cleanup
- [ ] Task: Prepare Hugging Face Dataset and Upload
    - [ ] (Manual/One-time) Create the public HF dataset (e.g., `user/render-tag-assets`)
    - [ ] (Manual/One-time) Upload current contents of `assets/` to the HF dataset
- [ ] Task: Clean up Git repository
    - [ ] Remove binary files from `assets/tags/`, `assets/models/`, `assets/textures/`, and `assets/hdri/`
    - [ ] Ensure `.gitkeep` files remain in each directory
    - [ ] Update `.gitignore` to exclude large binary files in these directories
    - [ ] Verify the repository size reduction and that `assets sync` restores the files correctly
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Migration and Repository Cleanup' (Protocol in workflow.md)
