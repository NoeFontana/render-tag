# Implementation Plan: Calibration & Ground Truth Suite (Phase 1)

## Phase 1: Experiment Infrastructure [checkpoint: 1311caf]
- [x] Task: Create Calibration Experiment Configurations [25cc5af]
    - [x] Create `configs/presets/calibration/01_checkerboard.yaml` (Static, uniform lighting, pinhole).
    - [x] Create `configs/presets/calibration/02_aprilgrid.yaml` (Slow rotation, 36h11).
    - [x] Create master `configs/experiments/locus_bench_p1.yaml` to orchestrate the hierarchical generation.
- [x] Task: Implement Hierarchical Pathing & Intent Metadata [25cc5af]
    - [x] Write failing tests for experiment output path construction (verifying the `data/locus_bench_v1/01_calibration/` structure).
    - [x] Update the experiment runner logic to handle nested hierarchy and inject `intent` into the context.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Experiment Infrastructure' (Protocol in workflow.md) [1311caf]
## Phase 2: High-Precision Annotations & Metadata [checkpoint: afd4444]
- [x] Task: Implement COCO-style Corner Ground Truth [82e7439]
    - [x] Write failing tests for projecting 3D corner coordinates to 2D COCO keypoints `[x, y, visibility]`.
    - [x] Implement corner extraction and annotation logic in `src/render_tag/data_io/annotations.py`.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Implement Dataset Fingerprinting and Manifest Injection [82e7439]
    - [x] Write failing tests for `dataset_info.json` generation (including SHA-256 fingerprinting).
    - [x] Implement metadata collector (provenance, geometry, versions) and writer.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 2: High-Precision Annotations & Metadata' (Protocol in workflow.md) [afd4444]

## Phase 3: Visualization & Quality Gate [checkpoint: c15f6a6]
- [x] Task: Enhance Visualization for Corner Markers [44af5f1]
    - [x] Write failing tests for `render-tag viz` to ensure it correctly parses and overlays COCO corners.
    - [x] Update visualization logic to support high-precision corner crosshairs.
    - [x] Verify tests pass and achieve >80% coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Visualization & Quality Gate' (Protocol in workflow.md) [c15f6a6]
