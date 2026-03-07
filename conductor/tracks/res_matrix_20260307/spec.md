# Track: Resolution Matrix Benchmarking (res_matrix_20260307)

## Overview
Introduce a parametric resolution matrix to the benchmarking pipeline. This allows for systematic evaluation of tag detection and localization across multiple resolutions (VGA to 4K) without maintaining separate configuration files.

## Functional Requirements
1. **CLI Overrides:** Implement dot-notation overrides in `render-tag generate` for nested Pydantic config values.
2. **Parametric Benchmarking Script:** Refactor `scripts/generate_benchmarks.sh` to iterate over a standard resolution matrix.
3. **Dynamic Camera Scaling:** Implement logic to automatically scale camera intrinsics (`fx`, `fy`, `cx`, `cy`) proportionally to resolution changes, maintaining a constant Field of View (FOV).
4. **Validation Hook:** Add pre-flight checks to ensure requested resolutions are mathematically valid for the camera sensor model.
5. **Output Taxonomy:** Standardize output directory structure (e.g., `outputs/benchmarks/<tag>/<resolution>/`).
6. **Hugging Face Integration:** Update CI/CD to push full-matrix datasets to the Hugging Face Hub during nightly/manual runs.

## Non-Functional Requirements
- **DRY Configuration:** Base YAML files remain untouched; all variations are handled via CLI overrides.
- **Resource Efficiency:** Tiered CI/CD execution to prevent bottlenecking pull request checks with high-resolution renders.
- **Backwards Compatibility:** Ensure existing benchmark runs (without resolution overrides) continue to function as expected.

## Acceptance Criteria
- `render-tag generate --override cameras[0].intrinsics.resolution=[1920,1080]` correctly updates the scene recipe.
- Proportional scaling of focal length and optical center is verified for a 4K override vs. a VGA base.
- `scripts/generate_benchmarks.sh` successfully generates images for all four target resolutions.
- CI workflow successfully triggers 640x480 renders on PR and skips higher resolutions.
- Documentation updated to explain the resolution matrix and override syntax.

## Out of Scope
- Support for non-standard aspect ratios (outside of the specified matrix).
- Implementation of new camera noise profiles specifically for 4K sensors.
