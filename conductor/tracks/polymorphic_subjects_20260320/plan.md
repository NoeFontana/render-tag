# Implementation Plan: Polymorphic Subject Architecture

## Phase 1: Infrastructure & Core Interface [checkpoint: 39c2990]
- [x] Task: Define the `AssetBuilder` Protocol and Registry 11e3b54
    - [x] Create `src/render_tag/backend/builders/__init__.py`.
    - [x] Define the `AssetBuilder` Protocol in `src/render_tag/backend/builders/interface.py`.
    - [x] Implement the `AssetRegistry` and `@register_builder` decorator in `src/render_tag/backend/builders/registry.py`.
- [x] Task: Write Tests for `AssetBuilder` and `AssetRegistry` 11e3b54
    - [x] Create `tests/unit/test_asset_builders.py`.
    - [x] Verify that the registry correctly maps subject types to builders.
    - [x] Test the auto-discovery mechanism (decorator).
- [x] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure & Core Interface' (Protocol in workflow.md) 39c2990

## Phase 2: Refactor Concrete Builders [checkpoint: ae14af5]
- [x] Task: Implement `TagBuilder` 2639b9f
    - [x] Create `src/render_tag/backend/builders/tag_builder.py`.
    - [x] Extract logic from `engine.py` to handle `TAG` creation.
    - [x] Verify that `TagBuilder` correctly attaches metadata and materials.
- [x] Task: Implement `CalibrationBoardBuilder` 2639b9f
    - [x] Create `src/render_tag/backend/builders/board_builder.py`.
    - [x] Extract logic from `engine.py` to handle `BOARD` creation.
    - [x] Verify that `CalibrationBoardBuilder` correctly handles both procedural and single-plane boards.
- [x] Task: Implement `NullBuilder` 2639b9f
    - [x] Create `src/render_tag/backend/builders/null_builder.py`.
    - [x] Implement a builder that returns an empty list or a simple mock object for testing.
- [x] Task: Write Tests for Concrete Builders 2639b9f
    - [x] Expand `tests/unit/test_asset_builders.py` to cover `TagBuilder` and `CalibrationBoardBuilder`.
    - [x] Verify that they produce valid Blender objects (via mocks or integration tests).
- [x] Task: Conductor - User Manual Verification 'Phase 2: Refactor Concrete Builders' (Protocol in workflow.md) ae14af5


## Phase 3: Engine Integration & Decoupling [checkpoint: 640d263]
- [x] Task: Refactor `RenderFacade.spawn_objects` 640d263
    - [x] Modify `src/render_tag/backend/engine.py` to use the `AssetRegistry`.
    - [x] Replace the monolithic loop with a lookup and `.build()` call.
    - [x] Ensure that \"Fail Hard\" behavior is implemented for missing builders.
- [x] Task: Verify Integration 640d263
    - [x] Run full scene generation to ensure objects are still spawned correctly.
    - [x] Run integration tests (`tests/integration/test_integration.py`).
- [x] Task: Conductor - User Manual Verification 'Phase 3: Engine Integration & Decoupling' (Protocol in workflow.md) 640d263

## Phase 4: Validation & Quality Gates
- [ ] Task: Verify Auto-Discovery
    - [ ] Ensure all builders are automatically registered during engine initialization.
- [ ] Task: Check Code Coverage
    - [ ] Target >80% coverage for the new `builders/` module.
- [ ] Task: Lint and Type Check
    - [ ] Run `ruff` and `ty` (or `mypy`) to ensure code quality.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Validation & Quality Gates' (Protocol in workflow.md)
