# Implementation Plan: High-Fidelity Calibration Targets

## Phase 1: The Configuration Contract (Schema)
- [ ] Task: Create `src/render_tag/core/schema/board.py` with `BoardType` and `BoardConfig`.
- [ ] Task: Implement Pydantic validators to enforce `marker_size < square_size` for ChArUco.
- [ ] Task: Write unit tests for schema parsing from YAML in `tests/unit/core/schema/test_board.py`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Schema and Core Configuration' (Protocol in workflow.md)

## Phase 2: The Texture Synthesizer (OpenCV Factory)
- [ ] Task: Implement `TextureFactory` in `src/render_tag/generation/texture_factory.py` using OpenCV.
- [ ] Task: Implement AprilGrid drawing logic with `spacing_ratio` support.
- [ ] Task: Implement ChArUco drawing logic (checkerboard + ArUco overlay).
- [ ] Task: Write tests to verify generated image dimensions and ID placement.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Texture Synthesizer' (Protocol in workflow.md)

## Phase 3: Scene Graph Integration (Blender Side)
- [ ] Task: Update `backend/scene.py` to support `create_board_plane` (single plane architecture).
- [ ] Task: Update `src/render_tag/generation/layouts.py` to support `BOARD` layout mode.
- [ ] Task: Ensure UV mapping is perfectly 1:1 in the backend engine.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Scene Integration' (Protocol in workflow.md)

## Phase 4: Calibration Ground Truth (Export)
- [ ] Task: Update `DetectionRecord` to handle multi-keypoint structures (Saddle Points vs Corners).
- [ ] Task: Implement `BoardConfig` writer to export `board_config.json`.
- [ ] Task: Update `COCOWriter` and `CSVWriter` to include the specific keypoint coordinates.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Data Export' (Protocol in workflow.md)

## Phase 5: Verification (The "Unit Test")
- [ ] Task: Implement the "Flat Test" verification script comparing theoretical vs. rendered pixel distances.
- [ ] Task: Perform projection sanity check (L2 error between 3D points and 2D pixels).
- [ ] Task: Conductor - User Manual Verification 'Phase 5: Verification' (Protocol in workflow.md)
