# Implementation Plan: Polymorphic Subject Architecture (Phase 1)

## Phase 1: Polymorphic Schema Definition
- [ ] Task: Write unit tests in `tests/unit/core/schema/test_subject.py` for polymorphic validation.
- [ ] Task: Create `src/render_tag/core/schema/subject.py` with `TagSubjectConfig` and `BoardSubjectConfig`.
- [ ] Task: Implement `SubjectConfig` as a Pydantic Discriminated Union.
- [ ] Task: Update `ScenarioConfig` in `src/render_tag/core/config.py` to replace loose fields with `subject: SubjectConfig`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Polymorphic Schema Definition' (Protocol in workflow.md)

## Phase 2: Host-Side Subject Decomposition
- [ ] Task: Write unit tests in `tests/unit/generation/test_compiler_polymorphism.py` for subject-to-recipe mapping.
- [ ] Task: Refactor `SceneCompiler` in `src/render_tag/generation/compiler.py` to extract subject-specific logic.
- [ ] Task: Implement a unified mapping from `SubjectConfig` to a generic `ObjectRecipe` (Mesh + Texture + 3D Keypoints).
- [ ] Task: Ensure `TagSubjectConfig` (Multiple Tags) is correctly flattened into the unified recipe format.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Host-Side Subject Decomposition' (Protocol in workflow.md)

## Phase 3: Generic Backend Execution & Projection
- [ ] Task: Write integration tests in `tests/integration/test_polymorphic_render.py` for end-to-end subject rendering.
- [ ] Task: Update `src/render_tag/backend/engine.py` to render subjects using the generic `ObjectRecipe` primitives.
- [ ] Task: Update `src/render_tag/backend/projection.py` to project the standardized 3D keypoint list into 2D pixel space.
- [ ] Task: Verify that "BOARD" and "TAGS" now share a 100% unified backend code path for spawning and ground-truth generation.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Generic Backend Execution & Projection' (Protocol in workflow.md)

## Phase 4: Versioning & Export Finalization
- [ ] Task: Increment `CURRENT_SCHEMA_VERSION` in `src/render_tag/core/constants.py` to enforce the breaking change.
- [ ] Task: Update `COCOWriter`, `CSVWriter`, and `RichTruthWriter` in `src/render_tag/data_io/writers.py` to consume the unified keypoint format.
- [ ] Task: Write verification tests to ensure 100% COCO compliance for keypoint annotations from polymorphic subjects.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Versioning & Export Finalization' (Protocol in workflow.md)
