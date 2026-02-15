# Specification: Dependency Injection for Randomness

## Overview
Even with global seeding, standard `random.*` or `numpy.random.*` calls are vulnerable to side effects from third-party libraries or internal state changes (like adding a log call that happens to trigger a random event). This track implements explicit dependency injection of a `numpy.random.Generator` instance to ensure absolute, pixel-perfect determinism.

## Functional Requirements
- **Explicit Injection:** Every sampling and stochastic function in `src/render_tag/generation/` must accept a `rng: numpy.random.Generator` argument.
- **Constructor Initialization:** The `Generator` class (`src/render_tag/generator.py`) will initialize the root `rng` in its `__init__` method using `np.random.default_rng(seed)`.
- **Banned Symbols:** Direct use of `import random` or global `numpy.random` functions is strictly prohibited in the generation layer.

## Non-Functional Requirements
- **Determinism:** Given the same seed, the sequence of generated values must be identical across runs, regardless of logging, timing, or external library state.
- **Enforcement:** The build/lint pipeline must fail if prohibited random modules are imported in the restricted scope.

## Acceptance Criteria
- [ ] A `numpy.random.Generator` is passed from the `Generator` class down to all sampling sub-modules.
- [ ] `import random` is removed from all files in `src/render_tag/generation/`.
- [ ] `.importlinter` is updated to block `random` in the generation layer.
- [ ] Running the generation twice with the same seed produces identical `scene_recipes.json` files.

## Out of Scope
- Refactoring the Blender-side scripts (backend) to use DI (Blender has its own random state management).
- Refactoring non-generation utilities (audit, IO) unless they perform stochastic operations.
