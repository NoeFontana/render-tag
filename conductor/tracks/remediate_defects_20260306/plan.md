# Implementation Plan: Remediate Mathematical and Structural Defects

## Phase 1: Mathematical and Geometric Integrity [checkpoint: eec9da6]
- [x] Task: Fix Camera Pose Math (Reflection Matrix Corruption) 4094324
    - [x] Write failing test in `tests/unit/test_pose_swizzle.py` proving determinant flips and invalid quaternions.
    - [x] Implement coordinate-axis swizzle in `calculate_relative_pose` and `get_opencv_camera_matrix`.
    - [x] Verify determinant remains +1 and quaternions are valid.
- [x] Task: Correct Z-Depth PPM Calculation ea92ee2
    - [x] Write failing test in `tests/unit/test_ppm_zdepth.py` demonstrating Euclidean distance error at FOV edges.
    - [x] Update `calculate_ppm` in `projection_math.py` to use orthogonal Z-depth.
    - [x] Verify PPM consistency across FOV.
- [x] Task: Strict Bounding Box Filtering 513c767
    - [x] Write failing test in `tests/unit/test_bbox_filtering.py` with points behind the camera.
    - [x] Implement strict filtering in `compute_bbox` (mark invalid if any corner is behind camera).
    - [x] Verify `-1e6` coordinates no longer corrupt bounding boxes.
- [x] Task: Fix Overlap Validation Logic b38e7b9
    - [x] Write failing test in `tests/unit/test_board_overlap.py` with 50% overlapping tags that currently pass.
    - [x] Correct `min_distance` check in `board.py` to use full `marker_size`.
    - [x] Verify overlapping tags are correctly rejected.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Mathematical and Geometric Integrity' (Protocol in workflow.md)

## Phase 2: Stability and Resource Management [checkpoint: 470e5a0]
- [x] Task: Implement Smart Texture Pooling 894fce7
    - [x] Write failing test in `tests/unit/test_texture_leak.py` counting Blender image datablocks during repeated floor generation.
    - [x] Implement image registry check in `setup_floor_material` (`scene.py`).
    - [x] Verify memory usage/datablock count remains constant for identical textures.
- [x] Task: Support Subject-Specific Normals 1ac06d0
    - [x] Write failing test in `tests/unit/test_subject_normals.py` using a non-Z-up asset that incorrectly fails occlusion checks.
    - [x] Extend `get_world_normal` and `check_tag_facing_camera` to respect `forward_axis` property.
    - [x] Update `SceneRecipe` schema to include optional `forward_axis`.
- [x] Task: ChArUco Standard ID Assignment (OpenCV Parity) a53f6b2
    - [x] Write failing test in `tests/unit/test_charuco_ids.py` comparing output against OpenCV standard dictionary layout.
    - [x] Refactor `compute_charuco_layout` to implement OpenCV-compatible assignment patterns.
    - [x] Verify detection parity with real-world OpenCV routines.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Stability and Resource Management' (Protocol in workflow.md)

## Phase 3: Pipeline and Execution Sync [checkpoint: 72709f5]
- [x] Task: Synchronize Subframe Rendering efd0089
    - [x] Write failing test in `tests/unit/test_motion_blur_sync.py` verifying timeline state at point of render call.
    - [x] Reorder `engine.py` render loop: call `frame_set(subframe=0.5)` *before* rendering.
    - [x] Verify motion blur and physics are correctly captured in output.
- [x] Task: Restore Raw Matrix Support (Reflection Preserving) 082e6b9
    - [x] Write failing test in `tests/unit/test_reflected_board.py` showing SVD corruption of intentionally flipped boards.
    - [x] Revert SVD reconstruction in `_get_scene_transformations`.
    - [x] Verify reflected ground truth matches reflected visual render.
- [x] Task: Defensive Subject Keypoint Handling 3f89e04
    - [x] Write failing test in `tests/unit/test_subject_keypoint_safety.py` using subjects with < 4 keypoints.
    - [x] Implement range checks in `generate_subject_records` and `format_coco_keypoints`.
    - [x] Verify system handles sparse keypoints without crashing.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Pipeline and Execution Sync' (Protocol in workflow.md)
