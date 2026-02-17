# Implementation Plan: "CV-Safe" Sampling Strategy

## Phase 1: Schema and Core Configuration
- [x] Task: Update `RendererConfig` schema in `src/render_tag/core/schema/renderer.py` to include `noise_threshold`, `max_samples`, `enable_denoising`, and `denoiser_type`. 52f621d
- [x] Task: Write TDD tests for `RendererConfig` validation in `tests/unit/core/schema/test_renderer.py`. 52f621d
- [x] Task: Implement validation and default values for the new fields. 52f621d
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Schema and Core Configuration' (Protocol in workflow.md)

## Phase 2: Backend Engine Integration
- [ ] Task: Update `src/render_tag/backend/engine.py` to apply adaptive sampling and denoising settings to the BlenderProc renderer.
- [ ] Task: Write TDD tests for the backend engine in `tests/unit/backend/test_engine.py` to verify BlenderProc calls.
- [ ] Task: Implement the logic to enable Intel OIDN with Albedo and Normal guidance in the engine.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Backend Engine Integration' (Protocol in workflow.md)

## Phase 3: Benchmarking and Sanity Checks
- [ ] Task: Create a "Sanity Check" script or test case that compares corner detection accuracy between high-sample and "CV-Safe" renders.
- [ ] Task: Update existing benchmark configuration files (e.g., `configs/test_minimal.yaml`) to use the new "CV-Safe" defaults.
- [ ] Task: Run a benchmark and verify performance improvement (reduced render time).
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Benchmarking and Sanity Checks' (Protocol in workflow.md)

## Phase 4: Documentation
- [ ] Task: Add a section to `docs/guide.md` or a new doc explaining the "CV-Safe" strategy and how to tune it.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Documentation' (Protocol in workflow.md)
