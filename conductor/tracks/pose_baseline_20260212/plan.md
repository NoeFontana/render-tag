# Implementation Plan: Pose Estimation Baseline (Phase 2)

## Phase 1: High-Precision Pose API & Schema [checkpoint: ad4b4d3]
- [x] Task: Define Contractual Dataset Schema [552bea7]
    - [x] Write failing tests for `dataset_info.json` validation against the new Pydantic contract.
    - [x] Implement `DatasetManifest` Pydantic model in `src/render_tag/orchestration/experiment_schema.py` including `camera_intrinsics`, `tag_specification` (with integer `tag_size_mm`), and `pose_convention`.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Implement Quaternion Pose Generation [552bea7]
    - [x] Write failing tests for converting 4x4 matrices to scalar-first `[w, x, y, z]` quaternions.
    - [x] Implement pose extraction logic in `src/render_tag/data_io/annotations.py` to produce the `position` and `rotation_quaternion` fields.
    - [x] Update `DetectionRecord` schema and `COCOWriter` to include these high-precision pose fields.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 1: High-Precision Pose API & Schema' (Protocol in workflow.md) [ad4b4d3]

## Phase 2: Declarative API Implementation (The Manifest)
- [x] Task: Create Clean Room Presets [a0e2f05]
    - [x] Create `configs/presets/apriltag/distance.yaml` (Static, 1m-30m sweep, ambient light).
    - [x] Create `configs/presets/apriltag/angle.yaml` (0-85 deg sweep, three-point light).
- [x] Task: Implement Master Experiment Manifest [a0e2f05]
    - [x] Create `configs/experiments/locus_pose_baseline.yaml` following the declarative Campaign structure.
    - [x] Write failing tests to ensure the Experiment runner correctly overrides `tag_size_mm` and injects `benchmark_phase` metadata.
    - [x] Update `expand_campaign` logic if necessary to support the new metadata injection requirements.
    - [x] Verify tests pass and achieve >80% coverage.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Declarative API Implementation (The Manifest)' (Protocol in workflow.md)

## Phase 3: Benchmark Generation & Verification
- [ ] Task: Generate Phase 2 Baseline Dataset
    - [ ] Execute `uv run render-tag experiment run configs/experiments/locus_pose_baseline.yaml`.
    - [ ] Verify directory structure: `output/locus_pose_baseline_v1/{02_pose_distance_sweep, 02_pose_angle_sweep}`.
- [ ] Task: Final Data Product Audit
    - [ ] Run `render-tag viz` on the generated datasets to verify corner/pose alignment.
    - [ ] Manually inspect `dataset_info.json` to confirm `pose_convention: "wxyz"` and integer `tag_size_mm`.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Benchmark Generation & Verification' (Protocol in workflow.md)
