# Implementation Plan - Test Suite Optimization

This plan reorganizes the test suite for better performance and enhances the "Shadow Render" loop to catch errors before Blender is launched.

## Phase 1: Test Reorganization [checkpoint: 676b90b]
**Goal:** Separate slow integration tests from fast unit tests.

- [~] Task: Create `tests/unit` and `tests/integration` subdirectories
- [x] Task: Reorganize existing tests 10dcb6b
    - [ ] Move `tests/test_integration.py`, `tests/test_industrial_pipeline.py`, and `tests/test_provenance_integration.py` to `tests/integration/`.
    - [ ] Move remaining functional tests to `tests/unit/`.
- [x] Task: Configure Pytest Markers 35d149e
    - [ ] Add `pytest.ini` or update `pyproject.toml` to define the `integration` marker.
    - [ ] Decorate all integration tests with `@pytest.mark.integration`.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Test Reorganization' (Protocol in workflow.md) 676b90b

## Phase 2: Enhanced "Pre-Flight" Validation
**Goal:** Catch configuration and geometric errors in the fast path.

- [ ] Task: Expand `RecipeValidator` utility
    - [ ] Extend `src/render_tag/tools/validator.py` to include asset existence checks.
    - [ ] Implement a fast 2D overlap detector for tags using AABB or OBB logic.
- [ ] Task: Integrate Validator into `generate` command
    - [ ] Update `src/render_tag/cli.py` to run the `RecipeValidator` before launching Blender (even when skip-render is not provided).
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Enhanced Pre-Flight Validation' (Protocol in workflow.md)

## Phase 3: Fast Integration Tests
**Goal:** Verify full pipeline logic using the `--skip-render` flag.

- [ ] Task: Create `tests/unit/test_cli_skip_render.py`
    - [ ] Write tests that run the full CLI with `--skip-render` and verify that recipes are generated correctly without Blender.
- [ ] Task: Update existing integration tests to include a \"Fast\" variant where applicable.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Fast Integration Tests' (Protocol in workflow.md)
