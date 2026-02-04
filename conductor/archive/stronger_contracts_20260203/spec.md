# Specification - Architecture: Stronger Contracts (The "Code" Layer)

## Overview
The current implementation uses Python `dataclasses` for internal schemas and configurations. While efficient for simple data containers, they lack robust validation, automatic type conversion, and serialization features necessary for a public tool. This track refactors the entire data layer to use **Pydantic v2**, establishing strong contracts between the user, the generator, and the renderer.

## Functional Requirements
- **Unified Pydantic Models:**
    - Migrate all classes in `src/render_tag/schema.py` (Scene Recipes) and `src/render_tag/config.py` (GenConfig) from `dataclasses` to Pydantic `BaseModel`.
    - Enforce strict typing and field constraints (e.g., `gt=0` for intensity, `Path` for file paths).
- **Strict Validation:**
    - Implement `model_validator` and `field_validator` where complex logic is required (e.g., ensuring ranges like `min_distance <= max_distance`).
    - The system MUST fail fast if a configuration or recipe is invalid.
- **Improved CLI Error Handling:**
    - Catch Pydantic `ValidationError` in `src/render_tag/cli.py` and display user-friendly error messages using `rich`.
- **Advanced Serialization:**
    - Use Pydantic's `model_dump(mode='json')` for serializing recipes to JSON for the Blender subprocess.
    - Ensure complex types like `Enum` and `Path` are handled automatically during serialization.

## Non-Functional Requirements
- **Minimal Performance Impact:** Pydantic v2 is highly optimized (written in Rust), so validation overhead should be negligible compared to rendering time.
- **Backward Compatibility (Configuration):** Existing YAML configuration files should still work, provided they adhere to the types defined in the new models.

## Acceptance Criteria
- [ ] All unit and integration tests pass after migration.
- [ ] Providing an invalid YAML config (e.g., string for an integer field) results in a clear error message instead of a crash.
- [ ] `SceneRecipe` JSON files produced by the generator are correctly parsed and executed by the Blender backend.
- [ ] No `dataclasses` remain in the core `schema.py` or `config.py` files.
