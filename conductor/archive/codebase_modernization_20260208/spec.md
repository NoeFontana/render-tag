# Specification: Codebase Modernization and Refactoring

## Overview
As the project scales from a prototype to a production-grade synthetic data generator, the codebase needs modernization to improve maintainability, performance, and robustness. This track focuses on refactoring core components, standardizing logging, and adopting modern Python/Pydantic best practices.

## Goals
- **Standardized Logging**: Replace scattered `print` statements with a unified logging system.
- **Pydantic V2 Optimization**: Use native V2 features for performance and clarity.
- **RNG Isolation**: Remove reliance on global random state to ensure thread-safety and better reproducibility.
- **Math Optimization**: Improve efficiency of seed generation and geometry calculations.

## Functional Requirements
- **Logging Infrastructure**:
    - Implement a central logging configuration in `src/render_tag/common/logging.py`.
    - Replace `print()` and `console.print()` in library code with `logger.info()`, `logger.debug()`, etc.
    - Keep `console.print()` only in the CLI layer for user-facing feedback.
- **Generator Refactoring**:
    - Use `random.Random` instances instead of global `random`.
    - Use `np.random.default_rng()` instead of global `np.random`.
    - Optimize `save_recipe_json` using `model_dump(mode="json")`.
- **Seed Management**:
    - Refactor `SeedManager.get_shard_seed` to use a non-looping deterministic hash (e.g., `hashlib.sha256`).
- **Pydantic V2 Migration**:
    - Ensure all `model_dump` calls use V2 syntax and features.

## Non-Functional Requirements
- **Maintainability**: Clearer separation between logic and side-effects (IO, global state).
- **Performance**: Reduced overhead in serialization and seed generation.
- **Testability**: Isolated RNGs make unit testing easier and more reliable.

## Acceptance Criteria
- [ ] No `print()` calls remaining in `src/render_tag/` (excluding `cli/`).
- [ ] Tests pass with 100% reproducibility.
- [ ] `SeedManager` generates seeds in O(1) time.
- [ ] All Pydantic models use `model_dump(mode="json")` for serialization.
