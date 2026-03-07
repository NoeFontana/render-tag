# Implementation Plan - Resolution Matrix Benchmarking (res_matrix_20260307)

## Phase 1: CLI Configuration Overrides [checkpoint: 2443215]
- [x] Task: Implement dot-notation override logic in `src/render_tag/cli/generate.py`. 2c022c9
    - [x] Write unit tests for nested Pydantic attribute updates via dot-notation.
    - [x] Implement the override parser and integration with Typer.
    - [x] Verify overrides correctly modify the base config without mutating the source YAML.
- [x] Task: Conductor - User Manual Verification 'CLI Overrides' (Protocol in workflow.md)

## Phase 2: Dynamic Camera Intrinsics Scaling [checkpoint: 6e298e5]
- [x] Task: Implement resolution-aware scaling of focal length and optical center in `src/render_tag/core/camera.py`. 5d41f35
    - [x] Write unit tests for constant-FOV scaling across multiple resolutions (VGA -> 4K).
    - [x] Add pre-flight validation to ensure scaled intrinsics are physically consistent.
    - [x] Integrate scaling logic into the `SceneRecipe` generation pipeline.
- [x] Task: Conductor - User Manual Verification 'Intrinsics Scaling' (Protocol in workflow.md)

## Phase 3: Benchmarking Pipeline Refactoring
- [ ] Task: Update `scripts/generate_benchmarks.sh` to support the resolution matrix.
    - [ ] Define the standard resolution array (VGA, 720p, 1080p, 4K).
    - [ ] Refactor existing benchmarking calls to iterate over the matrix.
    - [ ] Standardize output directory taxonomy.
- [ ] Task: Conductor - User Manual Verification 'Benchmarking Matrix' (Protocol in workflow.md)

## Phase 4: CI/CD Tiered Execution & Storage
- [ ] Task: Modify `.github/workflows/ci.yml` for tiered benchmarking.
    - [ ] Implement conditional logic to run only VGA benchmarks on PR.
    - [ ] Configure manual/nightly workflow for full-matrix generation.
    - [ ] Integrate Hugging Face Hub push logic for full-matrix artifacts.
- [ ] Task: Conductor - User Manual Verification 'CI/CD Tiering' (Protocol in workflow.md)
