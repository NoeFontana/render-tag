# Specification: Purge "Zombie Logic" (Dead Code Audit)

## Overview
Following the implementation of the "Move-Left" architecture and strict dependency injection for randomness, several files and logic blocks have become redundant. This track involves a comprehensive audit of the `src/render_tag/` directory to identify and permanently remove "Zombie Logic"—code that performs randomization or decision-making that has been superseded by the centralized `SceneCompiler`.

## Goals
- Eliminate non-deterministic logic from the rendering backend.
- Remove redundant files and legacy entry points.
- Reduce codebase complexity and cognitive load for developers.

## Functional Requirements
- **Backend Audit:** Scan `src/render_tag/backend/` for any imports of `random` or `numpy.random`. These must be removed, and the logic refactored to accept exact values from the `SceneRecipe`.
- **Logic Purge:** Identify and remove code blocks that branch based on randomization flags (e.g., `if config.randomize: ...`). The backend should now operate as a "pure" execution engine.
- **File Deletion:** Delete legacy generation files that are no longer in the primary call stack (e.g., `src/render_tag/generation/builder.py`).
- **Consolidation:** Ensure all decision-making logic is consolidated within `src/render_tag/generation/compiler.py`.

## Acceptance Criteria
- [ ] No files in `src/render_tag/backend/` import `random` or `numpy.random`.
- [ ] Redundant generation files (like `builder.py`) are deleted.
- [ ] The rendering pipeline still functions correctly using only absolute values from `SceneRecipe`.
- [ ] `uv run lint-imports` continues to pass with the existing determinism contracts.

## Out of Scope
- Refactoring `src/render_tag/core/resilience.py` (which uses `random` for retry jitter).
- Performance optimizations unrelated to dead code removal.
