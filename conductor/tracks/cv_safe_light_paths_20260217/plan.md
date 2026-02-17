# Implementation Plan: "CV-Safe" Light Paths Optimization

## Phase 1: Schema and Core Configuration [checkpoint: 7d068a2]
- [x] Task: Update `RendererConfig` schema in `src/render_tag/core/schema/renderer.py` to include light bounce parameters and the caustics toggle. cb77019
- [x] Task: Write TDD tests for `RendererConfig` in `tests/unit/core/schema/test_renderer.py` to verify defaults and override logic. cb77019
- [x] Task: Implement validation and Pydantic field defaults for the new parameters. cb77019
- [x] Task: Conductor - User Manual Verification 'Phase 1: Schema and Core Configuration' (Protocol in workflow.md)

## Phase 2: Backend Engine Integration [checkpoint: df31f3e]
- [x] Task: Update `src/render_tag/backend/engine.py` to apply `set_light_bounces` and `set_caustics` using values from the config. 98f9c97
- [x] Task: Write TDD tests for the backend engine in `tests/unit/backend/test_engine.py` to ensure BlenderProc methods are called correctly. 98f9c97
- [x] Task: Implement the logic in the engine to translate schema fields to BlenderProc renderer settings. 98f9c97
- [x] Task: Conductor - User Manual Verification 'Phase 2: Backend Engine Integration' (Protocol in workflow.md)

## Phase 3: Verification and Benchmarking
- [x] Task: Run a test render with the new "CV-Safe" defaults and verify that glossy highlights (glare) are still present on tags.
- [x] Task: Update benchmark configurations in `configs/` to reflect these optimizations as the new baseline.
- [x] Task: Compare render times before and after the optimization on a standard scene.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Verification and Benchmarking' (Protocol in workflow.md)

## Phase 4: Documentation
- [x] Task: Update `docs/architecture.md` or a relevant guide to document the light path optimization strategy.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Documentation' (Protocol in workflow.md)
