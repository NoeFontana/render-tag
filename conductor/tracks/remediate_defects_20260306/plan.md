# Implementation Plan: Remediate Mathematical and Structural Defects

## Phase 1: Mathematical and Geometric Integrity
- [x] Task: Fix Camera Pose Math (Reflection Matrix Corruption) 4094324
    - [ ] Write failing test in `tests/unit/test_pose_swizzle.py` proving determinant flips and invalid quaternions.
    - [ ] Implement coordinate-axis swizzle in `calculate_relative_pose` and `get_opencv_camera_matrix`.
    - [ ] Verify determinant remains +1 and quaternions are valid.
- [ ] Task: Correct Z-Depth PPM Calculation
    - [ ] Write failing test in `tests/unit/test_ppm_zdepth.py` demonstrating Euclidean distance error at FOV edges.
    - [ ] Update `calculate_ppm` in `projection_math.py` to use orthogonal Z-depth.
    - [ ] Verify PPM consistency across FOV.
- [ ] Task: Strict Bounding Box Filtering
    - [ ] Write failing test in `tests/unit/test_bbox_filtering.py` with points behind the camera.
    - [ ] Implement strict filtering in `compute_bbox` (mark invalid if any corner is behind camera).
    - [ ] Verify `-1e6` coordinates no longer corrupt bounding boxes.
- [ ] Task: Fix Overlap Validation Logic
    - [ ] Write failing test in `tests/unit/test_board_overlap.py` with 50% overlapping tags that currently pass.
    - [ ] Correct `min_distance` check in `board.py` to use full `marker_size`.
    - [ ] Verify overlapping tags are correctly rejected.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Mathematical and Geometric Integrity' (Protocol in workflow.md)

## Phase 2: Stability and Resource Management
- [ ] Task: Implement Smart Texture Pooling
    - [ ] Write failing test in `tests/unit/test_texture_leak.py` counting Blender image datablocks during repeated floor generation.
    - [ ] Implement image registry check in `setup_floor_material` (`scene.py`).
    - [ ] Verify memory usage/datablock count remains constant for identical textures.
- [ ] Task: Support Subject-Specific Normals
    - [ ] Write failing test in `tests/unit/test_subject_normals.py` using a non-Z-up asset that incorrectly fails occlusion checks.
    - [ ] Extend `get_world_normal` and `check_tag_facing_camera` to respect `forward_axis` property.
    - [ ] Update `SceneRecipe` schema to include optional `forward_axis`.
- [ ] Task: ChArUco Standard ID Assignment (OpenCV Parity)
    - [ ] Write failing test in `tests/unit/test_charuco_ids.py` comparing output against OpenCV standard dictionary layout.
    - [ ] Refactor `compute_charuco_layout` to implement OpenCV-compatible assignment patterns.
    - [ ] Verify detection parity with real-world OpenCV routines.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Stability and Resource Management' (Protocol in workflow.md)

## Phase 3: Pipeline and Execution Sync
- [ ] Task: Synchronize Subframe Rendering
    - [ ] Write failing test in `tests/unit/test_motion_blur_sync.py` verifying timeline state at point of render call.
    - [ ] Reorder `engine.py` render loop: call `frame_set(subframe=0.5)` *before* rendering.
    - [ ] Verify motion blur and physics are correctly captured in output.
- [ ] Task: Restore Raw Matrix Support (Reflection Preserving)
    - [ ] Write failing test in `tests/unit/test_reflected_board.py` showing SVD corruption of intentionally flipped boards.
    - [ ] Revert SVD reconstruction in `_get_scene_transformations`.
    - [ ] Verify reflected ground truth matches reflected visual render.
- [ ] Task: Defensive Subject Keypoint Handling
    - [ ] Write failing test in `tests/unit/test_subject_keypoint_safety.py` using subjects with < 4 keypoints.
    - [ ] Implement range checks in `generate_subject_records` and `format_coco_keypoints`.
    - [ ] Verify system handles sparse keypoints without crashing.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Pipeline and Execution Sync' (Protocol in workflow.md)
