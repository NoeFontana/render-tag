# Specification - Principal-Level Asset Management Roadmap

## Overview
This track implements a Single Source of Truth (SSoT) for binary assets (HDRIs, Textures, Tags, Models) to ensure hermetic reproducibility across all environments. It shifts the project from manual file management to a synchronization-based model using Hugging Face as the remote backend.

## Functional Requirements
- **AssetManager Interface:**
    - Develop a Python module using `huggingface_hub` for bidirectional sync.
    - Implement SHA-256 content hashing and version tracking (leveraging Hugging Face's LFS-compatible structure).
    - **Authentication:** Use the `HF_TOKEN` environment variable for all remote operations.
- **CLI Command Group (`render-tag assets`):**
    - `pull`: Fast, idempotent download of assets. Remote versions always overwrite local changes to ensure a consistent "cache view".
    - `push`: Atomic upload of local changes to the remote repository. Requires explicit authentication and preserves semantic commit history.
- **Directory Contract:**
    - Enforce a strict structure: `assets/hdri/`, `assets/textures/`, `assets/tags/`, and `assets/models/`.
    - Assets are treated as read-only during generation runtime.
- **Pre-Flight Asset Verification:**
    - Integrate a mandatory check into the `generate` command.
    - **Interactive Mode:** Prompt the user to pull missing assets.
    - **Headless Mode (CI):** Fail immediately if assets are missing or mismatched.

## Non-Functional Requirements
- **Smart Syncing:** Avoid redundant downloads by comparing local SHA-256 hashes with remote metadata.
- **Zero-Config Onboarding:** Enable a "clone and pull" workflow for new developers.
- **Auditability:** Maintain a traceable link between dataset versions and asset repository commit history.

## Acceptance Criteria
- [ ] `render-tag assets pull` successfully hydrates the `assets/` folder from Hugging Face.
- [ ] `render-tag generate` fails or prompts correctly if required assets are missing.
- [ ] Identical dataset results are produced on different machines after running `assets pull`.
- [ ] Asset uploads via `push` are atomic and authenticated.
