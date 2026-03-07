# Implementation Plan: Full Remediation of 10 Critical Architectural Bugs

## Phase 1: Core Geometric Contracts (Highest Priority) [checkpoint: 58593a1]
- [x] Task: Unify Winding Order Convention (865c21a)
    - [ ] Write failing tests in `tests/unit/test_annotations_winding.py` to confirm contradiction between `annotations.py` and `projection_math.py`.
    - [ ] Update `src/render_tag/core/annotations.py` to match the mathematical truth (Positive Area = CW).
    - [ ] Verify all tests pass and check coverage.
- [x] Task: Remove Dummy Visibility Data (b2b53df)
    - [ ] Write failing tests in `tests/unit/test_visibility_logic.py` for `skip_visibility` edge cases.
    - [ ] Delete hardcoded screen-size bounds and dummy `20.0` offsets in `engine.py` and `projection.py`.
    - [ ] Ensure `project_points` executes normally even when occlusion raycasting is skipped.
    - [ ] Verify all tests pass and check coverage.
- [x] Task: Persist Mesh Transformations (cdb4e5d)
    - [ ] Write failing tests in `tests/unit/test_scene_persistence.py` to check for non-unit scale on board planes.
    - [ ] Add `persist_transformation_into_mesh()` to `create_board_plane` in `src/render_tag/backend/scene.py`.
    - [ ] Verify board objects remain at `[1,1,1]` scale.
    - [ ] Verify all tests pass and check coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Geometric Contracts' (Protocol in workflow.md)

## Phase 2: Resolve Duplication & Spawning Conflicts [checkpoint: 5d86761]
- [x] Task: Implement Scene Graph Deduplication (2dbde44)
    - [ ] Write failing tests in `tests/integration/test_spawn_deduplication.py` for overlapping BOARD/TAG spawning.
    - [ ] Update `spawn_objects` in `src/render_tag/backend/engine.py` to suppress individual tags when a board is present.
    - [ ] Verify all tests pass and check coverage.
- [x] Task: Clean up Camera Pipeline (3c2b20b)
    - [ ] Write failing tests in `tests/unit/test_camera_pipeline.py` to detect duplicate pose injection.
    - [ ] Remove duplicate `add_camera_pose` call in `src/render_tag/backend/engine.py`.
    - [ ] Verify all tests pass and check coverage.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Resolve Duplication & Spawning Conflicts' (Protocol in workflow.md)

## Phase 3: Synchronize Ground Truth Extraction
- [x] Task: Remove SVD Scale-Stripping Hacks (fe81759)
    - [ ] Write failing tests in `tests/unit/test_projection_matrices.py` to ensure raw `world_matrix` parity.
    - [ ] Revert SVD hack in `_get_scene_transformations` within `src/render_tag/backend/projection.py`.
    - [ ] Verify all tests pass and check coverage.
- [ ] Task: Fix COCO Category Registration
    - [ ] Write failing tests in `tests/integration/test_coco_registration.py` for board marker dictionaries.
    - [ ] Modify `_setup_scene` in `src/render_tag/backend/engine.py` to register specific board marker families.
    - [ ] Verify all tests pass and check coverage.
- [ ] Task: Normalize Local Origins
    - [ ] Write failing tests in `tests/unit/test_board_layout_origins.py` for saddle point double-translation.
    - [ ] Update layout generation in `src/render_tag/generation/board.py` to center at `(0,0,0)`.
    - [ ] Verify all tests pass and check coverage.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Synchronize Ground Truth Extraction' (Protocol in workflow.md)
