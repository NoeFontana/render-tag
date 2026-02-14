# Implementation Plan: PPM-Driven Generation

## Phase 1: Schema and Contract Update [checkpoint: 1ffe64b]
- [x] Task: Define `PPMConstraint` and update `CameraConfig` 7977977
    - [x] Create `PPMConstraint` Pydantic model in `src/render_tag/core/config.py`
    - [x] Add `ppm_constraint` field to `CameraConfig`
    - [x] Implement validation logic to prioritize PPM over manual distance when present
- [x] Task: Conductor - User Manual Verification 'Phase 1: Schema and Contract Update' (Protocol in workflow.md) 1ffe64b

## Phase 2: Math Kernel Implementation
- [ ] Task: Write Tests for PPM Math
    - [ ] Create `tests/unit/test_ppm_math.py`
    - [ ] Define test cases for `calculate_ppm` and `solve_distance_for_ppm` with known constants
- [ ] Task: Implement PPM Solver in `projection_math.py`
    - [ ] Implement `calculate_ppm` logic
    - [ ] Implement `solve_distance_for_ppm` logic
    - [ ] Verify tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Math Kernel Implementation' (Protocol in workflow.md)

## Phase 3: Generator Logic Integration
- [ ] Task: Write Integration Tests for PPM Sampling
    - [ ] Create test case ensuring `SceneRecipeBuilder` produces distances consistent with PPM targets
- [ ] Task: Update `SceneRecipeBuilder.build_cameras`
    - [ ] Retrieve camera intrinsics (focal length)
    - [ ] Implement conditional sampling logic: PPM vs pure distance
    - [ ] Add safety clips against camera near/far planes
    - [ ] Verify integration tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Generator Logic Integration' (Protocol in workflow.md)

## Phase 4: Data Export and Auditing
- [ ] Task: Update Data Writers
    - [ ] Modify `DetectionRecord` to include `ppm` field
    - [ ] Update `CSVWriter` to include `ppm` column in `tags.csv`
    - [ ] Update `RichTruthWriter` to include `meta_ppm` in `rich_truth.json`
    - [ ] Update `SidecarWriter` to include PPM in image metadata
- [ ] Task: Update Auditing Pipeline
    - [ ] Modify `DatasetAuditor` to calculate PPM statistics using Polars
    - [ ] Update `AuditReport` schema and `DashboardGenerator` to visualize PPM distribution
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Data Export and Auditing' (Protocol in workflow.md)

## Phase 5: Verification and Benchmarking
- [ ] Task: Create PPM Sweep Benchmark Config
    - [ ] Create `configs/benchmarks/locus_ppm_sweep.yaml`
- [ ] Task: End-to-End Validation
    - [ ] Run generation with the new config
    - [ ] Audit the resulting dataset to confirm uniform PPM distribution
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Verification and Benchmarking' (Protocol in workflow.md)
