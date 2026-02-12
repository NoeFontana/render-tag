# Specification: Hugging Face Asset Migration

## Overview
Currently, binary assets (tags, 3D models, textures, HDRIs) are stored directly in the Git repository. This increases repository size and is not a scalable pattern for synthetic data generation. This track implements a migration of these assets to a public Hugging Face dataset and provides a mechanism to fetch them locally.

## Functional Requirements
- **Asset Migration**: All existing binary assets in `assets/` (tags, models, textures, hdri) will be moved to a public Hugging Face dataset.
- **Sync Command**: Implement `uv run render-tag assets sync` to download/update the local asset cache from the HF dataset.
- **On-Demand Loading**: The generator logic should check for the existence of required assets locally and download them from Hugging Face if missing during execution.
- **Git Cleanup**: Remove large binary files from the repository and update `.gitignore` to prevent future commits of these assets.
- **Placeholder Maintenance**: Keep the directory structure in `assets/` using `.gitkeep` files.

## Non-Functional Requirements
- **Efficiency**: Use `huggingface_hub` library for efficient, cached downloads.
- **Robustness**: Graceful handling of network failures or missing dataset files.

## Acceptance Criteria
- Running `uv run render-tag assets sync` successfully populates the `assets/` directory.
- Deleting a local asset and running a generation command triggers an automatic download of that specific asset.
- The repository size is significantly reduced after the migration and cleanup.
- `.gitignore` correctly blocks new binary assets from being staged.

## Out of Scope
- Automated uploading of new assets to Hugging Face (this remains a manual or separate administrative task for now).
- Support for private datasets requiring complex authentication (focus on the public dataset first).
