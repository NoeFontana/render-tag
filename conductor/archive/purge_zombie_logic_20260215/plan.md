# Implementation Plan: Purge "Zombie Logic" (Dead Code Audit)

## Phase 1: Discovery & Audit [checkpoint: ]
Scan the codebase to identify specific files and logic blocks that are no longer needed.

- [x] Task: Project-wide scan for `random` imports
    - [x] Run `grep` to find all imports of `random` and `numpy.random` in `src/render_tag/`.
    - [x] Log occurrences, excluding `core/resilience.py` and existing generation/compiler logic.
- [x] Task: Identify redundant files
    - [x] Verify if `src/render_tag/generation/builder.py` or similar files are still being imported.
    - [x] Check for unused Blender-side utility scripts in `src/render_tag/backend/`.
- [x] Task: Identify randomization branch logic
    - [x] Search for `if ...randomize` or similar flags in the backend rendering logic.
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Backend Purge [checkpoint: ]
Remove non-deterministic logic from the rendering workers.

- [x] Task: Cleanup `src/render_tag/backend/scene.py` (TDD)
    - [x] Write a test verifying that the backend scene setup correctly handles absolute values from a recipe.
    - [x] Remove any remaining random sampling or conditional randomization in `backend/scene.py`.
- [x] Task: Cleanup other backend modules
    - [x] Remove `random` imports and associated logic from other files in `src/render_tag/backend/`.
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Generation Consolidation [checkpoint: ]
Delete redundant files and simplify the generation package.

- [x] Task: Delete `src/render_tag/generation/builder.py`
    - [x] Confirm no other modules import it.
    - [x] Permanently delete the file.
- [x] Task: Remove other redundant generation utilities
    - [x] Delete any other identified "zombie" files in `src/render_tag/generation/`.
- [x] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Final Verification [checkpoint: ]
Ensure the system is clean and fully functional.

- [x] Task: Run full regression test suite
    - [x] Execute `uv run pytest` to ensure all functionality remains intact.
- [x] Task: Verify Import Linter
    - [x] Run `uv run lint-imports` to ensure no new violations were introduced.
- [x] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
