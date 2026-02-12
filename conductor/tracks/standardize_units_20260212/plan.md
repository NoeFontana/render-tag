# Implementation Plan: Standardize Tag Size to Meters (Float)

## Phase 1: Core Schema and Logic Standardization [checkpoint: c29f776]
- [x] Task: Update `DatasetManifest` model in `experiment_schema.py` [42c4ed6]
    - [x] Write failing tests in `tests/unit/test_dataset_manifest.py` for `tag_size_m` (float) and ensure `tag_size_mm` fails.
    - [x] Update `TagSpecificationManifest` in `src/render_tag/orchestration/experiment_schema.py` to use `tag_size_m: float`.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Update `dataset_info.py` generation logic [42c4ed6]
    - [x] Write failing tests in `tests/unit/test_dataset_info.py` to verify the presence of `tag_size_m` in the generated JSON.
    - [x] Update `generate_dataset_info` in `src/render_tag/audit/dataset_info.py` to map `size_meters` to `tag_size_m`.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Schema and Logic Standardization' (Protocol in workflow.md) [c29f776]

## Phase 2: Manifest Migration and Data Regeneration
- [ ] Task: Update Experiment Manifests and Presets
    - [ ] Update `configs/experiments/locus_pose_baseline.yaml` to use `tag_size_m: 0.16` (instead of 160).
    - [ ] Update `configs/presets/apriltag/distance.yaml` and `angle.yaml` if they contain the old field.
- [ ] Task: Regenerate Phase 2 Baseline Data
    - [ ] Execute `uv run render-tag experiment run configs/experiments/locus_pose_baseline.yaml`.
    - [ ] Verify `dataset_info.json` in the output folders contains the correct `tag_size_m` values.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Manifest Migration and Data Regeneration' (Protocol in workflow.md)
