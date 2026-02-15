# Implementation Plan: Dependency Injection for Randomness

## Phase 1: Infrastructure & Enforcement [checkpoint: 14cef88]
Establish the rules and foundation for deterministic sampling.

- [x] Task: Update `.importlinter` to block `random` in generation (TDD) (14cef88)
    - [x] Write failing test/verification that importing `random` in `src/render_tag/generation/` is forbidden.
    - [x] Update `.importlinter` configuration.
    - [x] Verify `uv run lint-imports` (or equivalent) fails if a violation is present.
- [x] Task: Update `Generator` to initialize root RNG (14cef88)
    - [x] Write unit test for `Generator.__init__` verifying RNG initialization from seed.
    - [x] Implement `self.rng = np.random.default_rng(seed)` in `Generator`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Refactoring Generation Modules [checkpoint: 29598d2]
Propagate the `rng` instance through the sampling call stack.

- [x] Task: Refactor `src/render_tag/generation/pose.py` (TDD) (bd9e6bc)
    - [x] Update tests to pass a mock/real RNG to pose sampling functions.
    - [x] Update `sample_pose` and related functions to accept and use `rng`.
- [x] Task: Refactor `src/render_tag/generation/sampling.py` (TDD) (bd9e6bc)
    - [x] Update tests to pass `rng`.
    - [x] Update stochastic functions to accept and use `rng`.
- [x] Task: Update `Generator.generate` call stack (bd9e6bc)
    - [x] Pass `self.rng` from `Generator` into the orchestration/generation calls.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Verification & Determinism [checkpoint: 29598d2]
Final audit to ensure pixel-perfect reproducibility.

- [x] Task: Verify Reproducibility Integration Test (29598d2)
    - [x] Create an integration test that runs the generator twice with the same seed.
    - [x] Assert that the generated `scene_recipes.json` files are identical.
- [x] Task: Final Lint & Cleanup (29598d2)
    - [x] Remove any dead `import random` statements.
    - [x] Ensure all docstrings reflect the new `rng` parameter.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
