# Implementation Plan: Subject Strategy Pattern (Phase 2)

## Phase 1: Strategy Protocol & Factory [checkpoint: 9e9537a]
- [x] Task: Write unit tests in `tests/unit/generation/test_subject_strategy_factory.py` for polymorphic strategy instantiation. 9e9537a
- [x] Task: Create `src/render_tag/generation/strategy/base.py` with `SubjectStrategy` (typing.Protocol). 9e9537a
- [x] Task: Implement `get_subject_strategy(config: SubjectConfig) -> SubjectStrategy` factory in `src/render_tag/generation/strategy/factory.py`. 9e9537a
- [x] Task: Conductor - User Manual Verification 'Phase 1: Strategy Protocol & Factory' (Protocol in workflow.md) 9e9537a

## Phase 2: TagStrategy Refactoring [checkpoint: e510a93]
- [x] Task: Write unit tests in `tests/unit/generation/test_tag_strategy.py` for pose sampling and asset preparation. e510a93
- [x] Task: Implement `TagStrategy` in `src/render_tag/generation/strategy/tags.py`. e510a93
- [x] Task: Refactor existing "Flying Tag" scattering and collision logic from `compiler.py` into `TagStrategy.sample_pose`. e510a93
- [x] Task: Ensure `TagStrategy.prepare_assets` correctly registers tag textures/materials. e510a93
- [x] Task: Conductor - User Manual Verification 'Phase 2: TagStrategy Refactoring' (Protocol in workflow.md) e510a93

## Phase 3: BoardStrategy Implementation [checkpoint: d4a186a]
- [x] Task: Write unit tests in `tests/unit/generation/test_board_strategy.py` for texture generation and scaling. d4a186a
- [x] Task: Implement `BoardStrategy` in `src/render_tag/generation/strategy/board.py`. d4a186a
- [x] Task: Implement `BoardStrategy.prepare_assets` to generate/cache board textures using `TextureFactory`. d4a186a
- [x] Task: Implement `BoardStrategy.sample_pose` to return a single 1x1 plane scaled to physical dimensions `(width_m, height_m, 1)`. d4a186a
- [x] Task: Conductor - User Manual Verification 'Phase 3: BoardStrategy Implementation' (Protocol in workflow.md) d4a186a

## Phase 4: Agnostic Compiler Refactor [checkpoint: a86c54a]
- [x] Task: Write unit tests in `tests/unit/generation/test_compiler_agnostic.py` to verify the compiler loop using mock strategies. a86c54a
- [x] Task: Refactor `SceneCompiler.compile_scenes` in `src/render_tag/generation/compiler.py` to use the `SubjectStrategy` interface. a86c54a
- [x] Task: Remove all `if/else` logic related to "Tags" vs. "Boards" from the core compilation loop. a86c54a
- [x] Task: Ensure the `SceneCompiler` correctly calls `prepare_assets` once and `sample_pose` per scene. a86c54a
- [x] Task: Conductor - User Manual Verification 'Phase 4: Agnostic Compiler Refactor' (Protocol in workflow.md) a86c54a

## Phase: Review Fixes
- [x] Task: Apply review suggestions f70a498
