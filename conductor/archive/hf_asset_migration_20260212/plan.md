# Implementation Plan: Hugging Face Asset Migration

## Phase 1: Infrastructure and HF Integration [checkpoint: aa04554]
- [x] Task: Add `huggingface_hub` dependency and update environment [784528b]
    - [x] Add `huggingface-hub` to `pyproject.toml`
    - [x] Verify installation and accessibility in the environment
- [x] Task: Create `AssetProvider` abstraction [642030f]
    - [x] Write failing tests for `AssetProvider` to handle local check and remote fetch
    - [x] Implement `AssetProvider` in `src/render_tag/data_io/assets.py` using `huggingface_hub`
    - [x] Verify tests pass and achieve >80% coverage
- [x] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure and HF Integration' (Protocol in workflow.md) [aa04554]

## Phase 2: CLI Sync Command Implementation [checkpoint: 85214da]
- [x] Task: Implement `assets sync` CLI command [9052f60]
    - [x] Write failing integration tests for `render-tag assets sync`
    - [x] Add `assets` group and `sync` command to `src/render_tag/cli/main.py`
    - [x] Implement full dataset download logic in the sync command
    - [x] Verify tests pass and achieve >80% coverage
- [x] Task: Conductor - User Manual Verification 'Phase 2: CLI Sync Command Implementation' (Protocol in workflow.md) [85214da]

## Phase 3: On-Demand Downloading and Generator Integration [checkpoint: d25b90c]
- [x] Task: Integrate `AssetProvider` into `Generator` [2db4fee]
    - [x] Write failing tests for `Generator` attempting to use a missing asset
    - [x] Modify `Generator` to use `AssetProvider` for resolving paths to tags, models, and textures
    - [x] Ensure automatic download triggers if the file is missing locally
    - [x] Verify tests pass and achieve >80% coverage
- [x] Task: Conductor - User Manual Verification 'Phase 3: On-Demand Downloading and Generator Integration' (Protocol in workflow.md) [d25b90c]

## Phase 4: Migration and Repository Cleanup [checkpoint: 21126b0]
- [x] Task: Prepare Hugging Face Dataset and Upload [manual]
    - [x] (Manual/One-time) Create the public HF dataset (e.g., `user/render-tag-assets`)
    - [x] (Manual/One-time) Upload current contents of `assets/` to the HF dataset
- [x] Task: Clean up Git repository [e7e751f]
    - [x] Remove binary files from `assets/tags/`, `assets/models/`, `assets/textures/`, and `assets/hdri/`
    - [x] Ensure `.gitkeep` files remain in each directory
    - [x] Update `.gitignore` to exclude large binary files in these directories
    - [x] Verify the repository size reduction and that `assets sync` restores the files correctly
- [x] Task: Conductor - User Manual Verification 'Phase 4: Migration and Repository Cleanup' (Protocol in workflow.md) [21126b0]
