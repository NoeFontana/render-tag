# Specification: Remediate Mathematical and Structural Defects

## 1. Overview
This track addresses 10 critical architectural and mathematical defects in the `render-tag` generator and renderer modules. These issues range from pose estimation corruption and memory leaks to incorrect validation logic and desynchronized rendering states.

## 2. Functional Requirements

### Phase 1: Mathematical and Geometric Integrity
- **Camera Pose Math:** Refactor `calculate_relative_pose` to use a coordinate-axis swizzle instead of a reflection matrix. This ensures the matrix determinant remains positive (+1) before quaternion extraction, preventing invalid or `NaN` pose data.
- **Z-Depth PPM:** Update `calculate_ppm` to use orthogonal Z-depth along the camera's optical axis instead of raw Euclidean distance.
- **Strict Bounding Box Filtering:** Update `compute_bbox` to mark a tag as invalid (invisible) if any single corner falls behind the camera plane or yields an invalid projection coordinate (`-1e6`).
- **Overlap Validation:** Correct the `min_distance` check in `board.py` from `marker_size * 0.5` to `marker_size` between square centers.

### Phase 2: Stability and Resource Management
- **Smart Texture Pooling:** Implement a texture registry in `scene.py` that checks for existing Blender image datablocks before loading from disk. This prevents OOM crashes during large-scale generation.
- **Subject-Specific Normals:** Extend `SceneRecipe` and `get_world_normal` to support a `forward_axis` parameter, allowing for correct occlusion and facing-camera checks for non-Z-up assets.
- **ChArUco Parity:** Refactor `compute_charuco_layout` to implement standard OpenCV ID assignment patterns, ensuring synthetic boards match real-world calibration targets.

### Phase 3: Pipeline and Execution Sync
- **Subframe Synchronization:** Reorder the render loop in `engine.py` to ensure `frame_set(subframe=0.5)` is called *before* the render execution, enabling motion blur and physics synchronization.
- **Reflection Support:** Revert SVD-based matrix reconstruction in `_get_scene_transformations`. Use the raw `world_matrix` directly to preserve intentional object reflections (e.g., flipped boards).
- **Keypoint Safety:** Implement defensive checks in `generate_subject_records` to handle generic `SUBJECT` types with fewer than 4 keypoints, preventing crashes in the COCO formatter.

## 3. Acceptance Criteria
- **Pose Accuracy:** Quaternions for camera poses must be normalized and non-NaN across all supported configurations.
- **Memory Stability:** Total Blender memory usage must remain relatively constant across 100+ scenes when using the same set of textures.
- **GT Precision:** Projected corners and bounding boxes must perfectly align with visual renders, even for objects at FOV edges or with intentional reflections.
- **Compatibility:** Synthetic ChArUco boards must be detectable using standard OpenCV detection routines.

## 4. Out of Scope
- Performance optimization of the raytracer itself.
- Adding new subject types beyond refining existing `TAG`, `BOARD`, and `SUBJECT` logic.
