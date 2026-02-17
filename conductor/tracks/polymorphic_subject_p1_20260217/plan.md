# Implementation Plan: Polymorphic Subject Architecture (Phase 1)

## Phase 1: Polymorphic Schema Definition [checkpoint: 01a86ee]
- [x] Task: Write unit tests in `tests/unit/core/schema/test_subject.py` for polymorphic validation. 01a86ee
- [x] Task: Create `src/render_tag/core/schema/subject.py` with `TagSubjectConfig` and `BoardSubjectConfig`. 01a86ee
- [x] Task: Implement `SubjectConfig` as a Pydantic Discriminated Union. 01a86ee
- [x] Task: Update `ScenarioConfig` in `src/render_tag/core/config.py` to replace loose fields with `subject: SubjectConfig`. 01a86ee
- [x] Task: Conductor - User Manual Verification 'Phase 1: Polymorphic Schema Definition' (Protocol in workflow.md) 01a86ee

## Phase 2: Host-Side Subject Decomposition [checkpoint: 1d67804]
- [x] Task: Write unit tests in `tests/unit/generation/test_compiler_polymorphism.py` for subject-to-recipe mapping. 1d67804
- [x] Task: Refactor `SceneCompiler` in `src/render_tag/generation/compiler.py` to extract subject-specific logic. 1d67804
- [x] Task: Implement a unified mapping from `SubjectConfig` to a generic `ObjectRecipe` (Mesh + Texture + 3D Keypoints). 1d67804
- [x] Task: Ensure `TagSubjectConfig` (Multiple Tags) is correctly flattened into the unified recipe format. 1d67804
- [x] Task: Conductor - User Manual Verification 'Phase 2: Host-Side Subject Decomposition' (Protocol in workflow.md) 1d67804

## Phase 3: Generic Backend Execution & Projection [checkpoint: 0c054ec]
- [x] Task: Write integration tests in `tests/integration/test_polymorphic_render.py` for end-to-end subject rendering. 0c054ec
- [x] Task: Update `src/render_tag/backend/engine.py` to render subjects using the generic `ObjectRecipe` primitives. 0c054ec
- [x] Task: Update `src/render_tag/backend/projection.py` to project the standardized 3D keypoint list into 2D pixel space. 0c054ec
- [x] Task: Verify that "BOARD" and "TAGS" now share a 100% unified backend code path for spawning and ground-truth generation. 0c054ec
- [x] Task: Conductor - User Manual Verification 'Phase 3: Generic Backend Execution & Projection' (Protocol in workflow.md) 0c054ec

## Phase 4: Versioning & Export Finalization [checkpoint: 4546933]
- [x] Task: Increment `CURRENT_SCHEMA_VERSION` in `src/render_tag/core/constants.py` to enforce the breaking change. 4546933
- [x] Task: Update `COCOWriter`, `CSVWriter`, and `RichTruthWriter` in `src/render_tag/data_io/writers.py` to consume the unified keypoint format. 0c054ec
- [x] Task: Write verification tests to ensure 100% COCO compliance for keypoint annotations from polymorphic subjects. 4546933
- [x] Task: Conductor - User Manual Verification 'Phase 4: Versioning & Export Finalization' (Protocol in workflow.md) 4546933

## Phase: Review Fixes
- [x] Task: Apply review suggestions 89fd1af
