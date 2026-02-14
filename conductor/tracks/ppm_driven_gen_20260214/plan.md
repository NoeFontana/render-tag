# Implementation Plan: PPM-Driven Generation

## Phase 1: Schema and Contract Update [checkpoint: 1ffe64b]
- [x] Task: Define `PPMConstraint` and update `CameraConfig` 7977977
    - [x] Create `PPMConstraint` Pydantic model in `src/render_tag/core/config.py`
    - [x] Add `ppm_constraint` field to `CameraConfig`
    - [x] Implement validation logic to prioritize PPM over manual distance when present
- [x] Task: Conductor - User Manual Verification 'Phase 1: Schema and Contract Update' (Protocol in workflow.md) 1ffe64b

## Phase 2: Math Kernel Implementation [checkpoint: 947401c]
- [x] Task: Write Tests for PPM Math 3dc1ecd
    - [x] Create `tests/unit/test_ppm_math.py`
    - [x] Define test cases for `calculate_ppm` and `solve_distance_for_ppm` with known constants
- [x] Task: Implement PPM Solver in `projection_math.py` 1ffe64b
    - [x] Implement `calculate_ppm` logic
    - [x] Implement `solve_distance_for_ppm` logic
    - [x] Verify tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 2: Math Kernel Implementation' (Protocol in workflow.md) 947401c

## Phase 3: Generator Logic Integration [checkpoint: 83e543a]
- [x] Task: Write Integration Tests for PPM Sampling 3dc1ecd
    - [x] Create test case ensuring `SceneRecipeBuilder` produces distances consistent with PPM targets
- [x] Task: Update `SceneRecipeBuilder.build_cameras` 1ffe64b
    - [x] Retrieve camera intrinsics (focal length)
    - [x] Implement conditional sampling logic: PPM vs pure distance
    - [x] Add safety clips against camera near/far planes
    - [x] Verify integration tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 3: Generator Logic Integration' (Protocol in workflow.md) 83e543a

## Phase 4: Data Export and Auditing [checkpoint: 0ee2a75]
- [x] Task: Update Data Writers 3dc1ecd
    - [x] Modify `DetectionRecord` to include `ppm` field
    - [x] Update `CSVWriter` to include `ppm` column in `tags.csv`
    - [x] Update `RichTruthWriter` to include `meta_ppm` in `rich_truth.json`
    - [x] Update `SidecarWriter` to include PPM in image metadata
- [x] Task: Update Auditing Pipeline 1ffe64b
    - [x] Modify `DatasetAuditor` to calculate PPM statistics using Polars
    - [x] Update `AuditReport` schema and `DashboardGenerator` to visualize PPM distribution
- [x] Task: Conductor - User Manual Verification 'Phase 4: Data Export and Auditing' (Protocol in workflow.md) 0ee2a75

## Phase 5: Verification and Benchmarking
- [ ] Task: Create PPM Sweep Benchmark Config
    - [ ] Create `configs/benchmarks/locus_ppm_sweep.yaml`
- [ ] Task: End-to-End Validation
    - [ ] Run generation with the new config
    - [ ] Audit the resulting dataset to confirm uniform PPM distribution
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Verification and Benchmarking' (Protocol in workflow.md)
