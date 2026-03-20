# Track spec.md

## Overview
This track focuses on reinforcing the "Parse, don't validate" principle by strictly separating legacy configuration handling from the core domain models and eliminating type erasure in the rendering engine. By extracting the Anti-Corruption Layer (ACL) and enforcing strict typing in the rendering pipeline, we ensure that the system's core is always working with pure, valid, and statically verifiable data.

## Functional Requirements
- **Extract Anti-Corruption Layer (ACL):**
    - Create a standalone `schema_adapter` module in `src/render_tag/core/`.
    - Move all backward-compatibility logic (`map_legacy_layout`, `_convert_flat_config`, `map_intent_to_scopes`, `map_legacy_seed`, `map_legacy_sensor_dynamics`) from `src/render_tag/core/config.py` to `schema_adapter.py`.
    - Implement a unified entry point in the adapter that translates raw legacy dictionaries into modern, v2-compliant dictionaries before they reach Pydantic models.
- **Pure Domain Models:**
    - Remove all `@model_validator(mode="before")` methods used for legacy mapping in `config.py`.
    - Ensure Pydantic models in `config.py` represent only the current, pure state of the domain.
- **Eliminate Type Erasure in Engine:**
    - Update `execute_recipe` in `src/render_tag/backend/engine.py` to strictly accept `SceneRecipe` as its input type.
    - Remove the `model_dump()` call at the entry point.
    - Cascade strict typing through internal functions (`_setup_scene`, `_render_camera_and_save`, `render_camera`).
    - Refactor dictionary-based lookups (e.g., `recipe_dict["cameras"]`) to attribute-based access (e.g., `recipe.cameras`).

## Non-Functional Requirements
- **Type Safety:** The entire rendering execution path must be statically verifiable by `mypy`.
- **Maintainability:** Refactoring the schema in the future should immediately flag breakages in the rendering logic during static analysis.
- **Performance:** Ensure that the transition from dictionary lookups to attribute access does not introduce regressions (it should be slightly faster or neutral).

## Acceptance Criteria
- [ ] All legacy configuration variants (flat layout, legacy intent, etc.) are correctly migrated by the `schema_adapter` and successfully validated by the core models.
- [ ] `src/render_tag/core/config.py` contains no backward-compatibility mapping logic.
- [ ] `src/render_tag/backend/engine.py` and its internal functions use attribute access for `SceneRecipe` and its components.
- [ ] `mypy src/render_tag` passes with zero errors related to `SceneRecipe` type erasure.
- [ ] All existing tests pass, including those using legacy configuration files.
- [ ] New unit tests verify the `schema_adapter` isolation and correctness.

## Out of Scope
- Major architectural changes to the rendering backend beyond type-safety refactoring.
- Introduction of new configuration features or fields.
