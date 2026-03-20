# Implementation Plan: Polymorphic Subject Architecture

## Phase 1: Infrastructure & Core Interface
- [ ] Task: Define the `AssetBuilder` Protocol and Registry
    - [ ] Create `src/render_tag/backend/builders/__init__.py`.
    - [ ] Define the `AssetBuilder` Protocol in `src/render_tag/backend/builders/interface.py`.
    - [ ] Implement the `AssetRegistry` and `@register_builder` decorator in `src/render_tag/backend/builders/registry.py`.
- [ ] Task: Write Tests for `AssetBuilder` and `AssetRegistry`
    - [ ] Create `tests/unit/test_asset_builders.py`.
    - [ ] Verify that the registry correctly maps subject types to builders.
    - [ ] Test the auto-discovery mechanism (decorator).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Infrastructure & Core Interface' (Protocol in workflow.md)

## Phase 2: Refactor Concrete Builders
- [ ] Task: Implement `TagBuilder`
    - [ ] Create `src/render_tag/backend/builders/tag_builder.py`.
    - [ ] Extract logic from `engine.py` to handle `TAG` creation.
    - [ ] Verify that `TagBuilder` correctly attaches metadata and materials.
- [ ] Task: Implement `CalibrationBoardBuilder`
    - [ ] Create `src/render_tag/backend/builders/board_builder.py`.
    - [ ] Extract logic from `engine.py` to handle `BOARD` creation.
    - [ ] Verify that `CalibrationBoardBuilder` correctly handles both procedural and single-plane boards.
- [ ] Task: Implement `NullBuilder`
    - [ ] Create `src/render_tag/backend/builders/null_builder.py`.
    - [ ] Implement a builder that returns an empty list or a simple mock object for testing.
- [ ] Task: Write Tests for Concrete Builders
    - [ ] Expand `tests/unit/test_asset_builders.py` to cover `TagBuilder` and `CalibrationBoardBuilder`.
    - [ ] Verify that they produce valid Blender objects (via mocks or integration tests).
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Refactor Concrete Builders' (Protocol in workflow.md)

## Phase 3: Engine Integration & Decoupling
- [ ] Task: Refactor `RenderFacade.spawn_objects`
    - [ ] Modify `src/render_tag/backend/engine.py` to use the `AssetRegistry`.
    - [ ] Replace the monolithic loop with a lookup and `.build()` call.
    - [ ] Ensure that \"Fail Hard\" behavior is implemented for missing builders.
- [ ] Task: Verify Integration
    - [ ] Run full scene generation to ensure objects are still spawned correctly.
    - [ ] Run integration tests (`tests/integration/test_integration.py`).
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Engine Integration & Decoupling' (Protocol in workflow.md)

## Phase 4: Validation & Quality Gates
- [ ] Task: Verify Auto-Discovery
    - [ ] Ensure all builders are automatically registered during engine initialization.
- [ ] Task: Check Code Coverage
    - [ ] Target >80% coverage for the new `builders/` module.
- [ ] Task: Lint and Type Check
    - [ ] Run `ruff` and `ty` (or `mypy`) to ensure code quality.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Validation & Quality Gates' (Protocol in workflow.md)
