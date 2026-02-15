# Implementation Plan: Dependency Injection for Randomness

## Phase 1: Infrastructure & Enforcement [checkpoint: ]
Establish the rules and foundation for deterministic sampling.

- [ ] Task: Update `.importlinter` to block `random` in generation (TDD)
    - [ ] Write failing test/verification that importing `random` in `src/render_tag/generation/` is forbidden.
    - [ ] Update `.importlinter` configuration.
    - [ ] Verify `uv run lint-imports` (or equivalent) fails if a violation is present.
- [ ] Task: Update `Generator` to initialize root RNG
    - [ ] Write unit test for `Generator.__init__` verifying RNG initialization from seed.
    - [ ] Implement `self.rng = np.random.default_rng(seed)` in `Generator`.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Refactoring Generation Modules [checkpoint: ]
Propagate the `rng` instance through the sampling call stack.

- [ ] Task: Refactor `src/render_tag/generation/pose.py` (TDD)
    - [ ] Update tests to pass a mock/real RNG to pose sampling functions.
    - [ ] Update `sample_pose` and related functions to accept and use `rng`.
- [ ] Task: Refactor `src/render_tag/generation/sampling.py` (TDD)
    - [ ] Update tests to pass `rng`.
    - [ ] Update stochastic functions to accept and use `rng`.
- [ ] Task: Update `Generator.generate` call stack
    - [ ] Pass `self.rng` from `Generator` into the orchestration/generation calls.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Verification & Determinism [checkpoint: ]
Final audit to ensure pixel-perfect reproducibility.

- [ ] Task: Verify Reproducibility Integration Test
    - [ ] Create an integration test that runs the generator twice with the same seed.
    - [ ] Assert that the generated `scene_recipes.json` files are identical.
- [ ] Task: Final Lint & Cleanup
    - [ ] Remove any dead `import random` statements.
    - [ ] Ensure all docstrings reflect the new `rng` parameter.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)
