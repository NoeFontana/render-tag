# Track plan.md

## Phase 1: Extract Anti-Corruption Layer (ACL)
- [x] Task: Implement `src/render_tag/core/schema_adapter.py` a7fca0c
    - [x] Create basic module structure and export a unified `adapt_config` function.
    - [x] Integrate/Merge `src/render_tag/core/migration.py` into `schema_adapter.py` (or rename it).
    - [x] Implement `_convert_flat_config` (moved from `config.py`).
    - [x] Implement `map_intent_to_scopes` (moved from `config.py`).
    - [x] Implement `map_legacy_seed` (moved from `config.py`).
    - [x] Implement `map_legacy_sensor_dynamics` (moved from `config.py`).
    - [x] Implement `migrate_legacy_layout` (moved from `config.py`).
- [ ] Task: Refactor `src/render_tag/core/config.py`
    - [ ] Remove legacy mapping functions and their Pydantic validators.
    - [ ] Update `load_config_from_yaml` to use `schema_adapter.adapt_config` before validation.
- [ ] Task: Verify ACL Correctness
    - [ ] Write tests in `tests/unit/test_schema_adapter.py` verifying each transformation.
    - [ ] Ensure `configs/archive/locus_bench_p1.yaml` (if available) or other legacy configs pass through correctly.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Extract ACL' (Protocol in workflow.md)

## Phase 2: Eliminate Type Erasure in Rendering Engine
- [ ] Task: Refactor `src/render_tag/backend/engine.py` Entry Point
    - [ ] Update `execute_recipe` to strictly accept `SceneRecipe`.
    - [ ] Remove `recipe.model_dump()` and all references to `recipe_dict` in `execute_recipe`.
- [ ] Task: Cascade Strict Typing through Internal Engine Functions
    - [ ] Refactor `_setup_scene` to use attribute-based access on `SceneRecipe`.
    - [ ] Refactor `_render_camera_and_save` to use attribute-based access on `SceneRecipe` and its components.
    - [ ] Refactor `render_camera` to use attribute-based access on its input recipe.
- [ ] Task: Verify Engine Type Safety and Functionality
    - [ ] Run `mypy` and fix all typing errors in the engine.
    - [ ] Run integration tests to ensure rendering still works correctly.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Eliminate Type Erasure' (Protocol in workflow.md)
