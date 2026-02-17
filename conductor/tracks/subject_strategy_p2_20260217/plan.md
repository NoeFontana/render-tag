# Implementation Plan: Subject Strategy Pattern (Phase 2)

## Phase 1: Strategy Protocol & Factory
- [ ] Task: Write unit tests in `tests/unit/generation/test_subject_strategy_factory.py` for polymorphic strategy instantiation.
- [ ] Task: Create `src/render_tag/generation/strategy/base.py` with `SubjectStrategy` (typing.Protocol).
- [ ] Task: Implement `get_subject_strategy(config: SubjectConfig) -> SubjectStrategy` factory in `src/render_tag/generation/strategy/factory.py`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Strategy Protocol & Factory' (Protocol in workflow.md)

## Phase 2: TagStrategy Refactoring
- [ ] Task: Write unit tests in `tests/unit/generation/test_tag_strategy.py` for pose sampling and asset preparation.
- [ ] Task: Implement `TagStrategy` in `src/render_tag/generation/strategy/tags.py`.
- [ ] Task: Refactor existing "Flying Tag" scattering and collision logic from `compiler.py` into `TagStrategy.sample_pose`.
- [ ] Task: Ensure `TagStrategy.prepare_assets` correctly registers tag textures/materials.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: TagStrategy Refactoring' (Protocol in workflow.md)

## Phase 3: BoardStrategy Implementation
- [ ] Task: Write unit tests in `tests/unit/generation/test_board_strategy.py` for texture generation and scaling.
- [ ] Task: Implement `BoardStrategy` in `src/render_tag/generation/strategy/board.py`.
- [ ] Task: Implement `BoardStrategy.prepare_assets` to generate/cache board textures using `TextureFactory`.
- [ ] Task: Implement `BoardStrategy.sample_pose` to return a single 1x1 plane scaled to physical dimensions `(width_m, height_m, 1)`.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: BoardStrategy Implementation' (Protocol in workflow.md)

## Phase 4: Agnostic Compiler Refactor
- [ ] Task: Write unit tests in `tests/unit/generation/test_compiler_agnostic.py` to verify the compiler loop using mock strategies.
- [ ] Task: Refactor `SceneCompiler.compile_scenes` in `src/render_tag/generation/compiler.py` to use the `SubjectStrategy` interface.
- [ ] Task: Remove all `if/else` logic related to "Tags" vs. "Boards" from the core compilation loop.
- [ ] Task: Ensure the `SceneCompiler` correctly calls `prepare_assets` once and `sample_pose` per scene.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Agnostic Compiler Refactor' (Protocol in workflow.md)
