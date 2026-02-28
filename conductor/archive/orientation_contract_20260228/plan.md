# Implementation Plan: 3D-Anchored Orientation Contract

This plan enforces a strict 3D local-space asset contract to ensure perfect orientation preservation in tag ground truth.

## Phase 1: Formalize the Geometric Contract [checkpoint: 9d5785d]
- [x] Task: Update `ARCHITECTURE.md` to define the 'Logical Corner 0' rule and clockwise winding in 3D local space. 6c89c7e
- [x] Task: Add technical docstrings to `src/render_tag/backend/assets.py` and `src/render_tag/backend/projection.py` explaining the contract. 1538be2
- [x] Task: Conductor - User Manual Verification 'Phase 1: Formalize the Geometric Contract' (Protocol in workflow.md) 9d5785d


## Phase 2: Update Asset Generation (TDD) [checkpoint: a3a7712]
- [x] Task: Create `tests/unit/heavy_logic/backend/test_orientation_assets.py` to verify `keypoints_3d` assignment in logical order. 10be243
- [x] Task: Modify `create_tag_plane` in `src/render_tag/backend/assets.py` to assign `keypoints_3d` property. 10be243
- [x] Task: Remove legacy `corner_coords` logic and update `get_corner_world_coords` to use `keypoints_3d`. 10be243
- [x] Task: Conductor - User Manual Verification 'Phase 2: Update Asset Generation' (Protocol in workflow.md) a3a7712

## Phase 3: Purify Projection Engine (TDD) [checkpoint: f505006]
- [x] Task: Create `tests/unit/core_logic/math/test_orientation_projection.py` to verify projection without image-space sorting. 93dfb27
- [x] Task: Remove `sort_corners` function and its calls from `src/render_tag/backend/projection.py`. 93dfb27
- [x] Task: Update `generate_subject_records` and `_process_board_tags` to strictly follow 3D keypoint indices. 93dfb27
- [x] Task: Conductor - User Manual Verification 'Phase 3: Purify Projection Engine' (Protocol in workflow.md) f505006

## Phase 4: Invariance Test Suite [checkpoint: 900b973]
- [x] Task: Implement `tests/integration/test_orientation_invariance.py` with Upright, Inverted (180 roll), and extreme Skew cases. d79e918
- [x] Task: Run full generation pipeline audit to ensure zero orientation loss. d79e918
- [x] Task: Conductor - User Manual Verification 'Phase 4: Invariance Test Suite' (Protocol in workflow.md) 900b973
