# Implementation Plan - Rolling Shutter Simulation

This plan implements rolling shutter effects in the Cycles renderer to bridge the sim-to-real gap for robotics applications.

## Phase 1: Schema & Configuration Update
**Goal:** Define the data contract for rolling shutter duration and organize sensor dynamics.

- [~] Task: Write Tests for Schema Validation
    - [ ] Add tests to `tests/unit/test_config.py` for `rolling_shutter_duration_ms`.
    - [ ] Verify validation logic (non-negative, range checks).
- [ ] Task: Update `CameraConfig` and `SceneRecipe`
    - [ ] Refactor `CameraConfig` in `src/render_tag/config.py` to group sensor dynamics.
    - [ ] Update `SceneRecipe` in `src/render_tag/schema.py` to include the new field.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Schema & Configuration Update' (Protocol in workflow.md)

## Phase 2: Blender Backend Implementation
**Goal:** Map the configuration to Blender's rendering engine settings.

- [~] Task: Write Backend Mapping Tests (Mocks)
    - [ ] Create tests in `tests/unit/test_geometry_camera.py` verifying the value propagation.
- [x] Task: Implement Rolling Shutter in `backend/camera.py` 0264e97
    - [ ] Update camera setup logic to set `bpy.context.scene.render.rolling_shutter_duration`.
    - [ ] Implement engine check logic to issue warnings for Eevee/Workbench.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Blender Backend Implementation' (Protocol in workflow.md)

## Phase 3: Integration & Physical Validation
**Goal:** Verify the geometric shearing effect through end-to-end rendering.

- [ ] Task: Create Rolling Shutter Integration Test
    - [ ] Implement `tests/integration/test_rolling_shutter_distortion.py`.
    - [ ] Setup a scene with a high-velocity tag and assert geometric shearing in the resulting render (Shadow/Mock verify vs Cycles actual).
- [ ] Task: Verify Ground Truth Alignment
    - [ ] Ensure that even with warping, corner annotations match the mid-exposure pose.
- [ ] Task: Run Full Test Suite
    - [ ] Ensure no regressions in existing motion blur or camera logic.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Integration & Physical Validation' (Protocol in workflow.md)
