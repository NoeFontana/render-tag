# Implementation Plan - Refine Industrial Rendering & Sensor Simulation

This plan focuses on enhancing the photorealism and sensor accuracy of the `render-tag` pipeline.

## Phase 1: Advanced Sensor Noise & Motion Blur [checkpoint: ae025f4]
**Goal:** Implement realistic camera artifacts to minimize the sim-to-real gap.

- [x] Task: Implement Parametric Sensor Noise Models 70f7958
    - [ ] Create `SensorNoiseConfig` Pydantic model in `src/render_tag/schema.py` supporting Gaussian, Poisson, and Salt-and-Pepper parameters.
    - [ ] Implement noise generation logic in `src/render_tag/backend/camera.py` (or a new `sensors.py` module).
    - [ ] Write unit tests for noise generation functions to ensure statistical correctness.
    - [ ] Integrate noise application into the rendering pipeline in `src/render_tag/backend/executor.py`.
- [x] Task: Refine Procedural Motion Blur 4875cb8
    - [ ] Update `CameraConfig` in `src/render_tag/schema.py` to include exposure time and velocity parameters.
    - [ ] Implement motion blur calculation logic in `src/render_tag/backend/camera.py` utilizing Blender's motion blur settings.
    - [ ] Write unit tests verifying that higher velocity/exposure time results in increased blur values.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Advanced Sensor Noise & Motion Blur' (Protocol in workflow.md) ae025f4

## Phase 2: Industrial Lighting & Surface Imperfections [checkpoint: 178e2e7]
**Goal:** Create realistic industrial environments and tag wear-and-tear.

- [x] Task: Industrial HDRi Lighting Presets 4ebe3bb
    - [ ] Define new `LightingConfig` presets for "Factory", "Warehouse", and "Outdoor Industrial" in `src/render_tag/config.py` (or yaml configs).
    - [ ] Ensure `src/render_tag/backend/scene.py` correctly loads and applies these HDRi maps.
    - [ ] Validate that lighting intensity and rotation are randomized within realistic bounds.
- [x] Task: Procedural Surface Imperfections 347a215
    - [ ] Create `TagSurfaceConfig` in `src/render_tag/schema.py` for scratches, dust, and specularity.
    - [ ] Implement material shader modification logic in `src/render_tag/backend/assets.py` to apply these textures to tag meshes.
    - [ ] Write tests ensuring that surface imperfection parameters correctly modify the material node tree in Blender.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Industrial Lighting & Surface Imperfections' (Protocol in workflow.md) 178e2e7

## Phase 3: Integration & Validation [checkpoint: dfa191c]
**Goal:** Verify the complete pipeline and ensure data integrity.

- [x] Task: Update "Shadow Render" for New Features 0493277
    - [ ] Update `src/render_tag/generator.py` (and visualization tools) to approximate/visualize noise and lighting in the 2D preview.
    - [ ] Ensure `validate-recipe` command covers the new configuration parameters.
- [x] Task: Full Pipeline Integration Test b04fc4d
    - [ ] Create an integration test `tests/test_industrial_pipeline.py` that runs a full generation cycle with new features enabled.
    - [ ] Verify that output images are generated and annotations are correct (bounding boxes match visible tags).
- [x] Task: Conductor - User Manual Verification 'Phase 3: Integration & Validation' (Protocol in workflow.md) dfa191c
