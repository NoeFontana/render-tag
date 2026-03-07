# Specification: Full Remediation of 10 Critical Architectural Bugs

## 1. Overview
A deep architectural review has identified 10 critical misalignments between the Blender scene graph, the Python mathematical projection layer, and the data serialization layer. This track aims to fully remediate these issues through a 3-phase execution strategy to ensure mathematical accuracy and rendering integrity.

## 2. Goals
- Standardize the coordinate system and winding order (OpenCV Y-down, Positive Area = CW).
- Eliminate geometric drift by ensuring all mesh transformations are persisted (unscaled [1,1,1] meshes).
- Resolve object duplication (Z-fighting) and camera pipeline corruption.
- Synchronize ground truth extraction with the unified scene graph.
- Fix COCO category registration and local origin normalization.

## 3. Functional Requirements
### Phase 1: Core Geometric Contracts (Highest Priority)
1. **Winding Order Unification:** Standardize on OpenCV Y-down across the codebase. Update `annotations.py` to match `projection_math.py` (Positive Area = CW).
2. **Remove Dummy Data:** Delete hardcoded screen-size bounds and `20.0` offsets in `engine.py` and `projection.py`. `skip_visibility` must only bypass raycast occlusion.
3. **Persist Mesh Transforms:** Add `persist_transformation_into_mesh()` to `create_board_plane` to ensure [1,1,1] scale for physics and raycasting.

### Phase 2: Resolve Duplication & Spawning Conflicts
4. **Scene Graph Deduplication:** Update `spawn_objects` in `engine.py` to suppress individual `TAG` objects when a `BOARD` with a composite texture is present.
5. **Clean up Camera Pipeline:** Remove the duplicate `add_camera_pose` call in `engine.py`.

### Phase 3: Synchronize Ground Truth Extraction
6. **Remove SVD Hacks:** Revert the scale-stripping SVD hack in `_get_scene_transformations` as meshes will now be unscaled.
7. **Fix COCO Registration:** Modify `_setup_scene` to register specific board marker dictionaries (e.g., `tag36h11`) to the COCO writer.
8. **Normalize Local Origins:** Ensure `board.py` generates layouts centered at `(0,0,0)`, delegating translation to the `world_matrix`.

## 4. Acceptance Criteria
- **Regression Tests:** 10 new tests (one per bug) must pass, confirming the fix for each identified issue.
- **Existing Tests:** All 391 pre-existing tests must pass.
- **Visual Audit:** Manual verification via `render-tag viz recipe` for ChArUco and AprilGrid boards must show zero Z-fighting and perfect corner alignment.
- **Winding Order:** All projected corners must follow the CW winding order consistently.

## 5. Out of Scope
- Adding new subject types or features not related to the 10 identified bugs.
- Performance optimization beyond what is necessary to fix these bugs.
