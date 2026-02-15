# Implementation Plan: Purge "Zombie Logic" (Dead Code Audit)

## Phase 1: Discovery & Audit [checkpoint: ]
Scan the codebase to identify specific files and logic blocks that are no longer needed.

- [ ] Task: Project-wide scan for `random` imports
    - [ ] Run `grep` to find all imports of `random` and `numpy.random` in `src/render_tag/`.
    - [ ] Log occurrences, excluding `core/resilience.py` and existing generation/compiler logic.
- [ ] Task: Identify redundant files
    - [ ] Verify if `src/render_tag/generation/builder.py` or similar files are still being imported.
    - [ ] Check for unused Blender-side utility scripts in `src/render_tag/backend/`.
- [ ] Task: Identify randomization branch logic
    - [ ] Search for `if ...randomize` or similar flags in the backend rendering logic.
- [ ] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Backend Purge [checkpoint: ]
Remove non-deterministic logic from the rendering workers.

- [ ] Task: Cleanup `src/render_tag/backend/scene.py` (TDD)
    - [ ] Write a test verifying that the backend scene setup correctly handles absolute values from a recipe.
    - [ ] Remove any remaining random sampling or conditional randomization in `backend/scene.py`.
- [ ] Task: Cleanup other backend modules
    - [ ] Remove `random` imports and associated logic from other files in `src/render_tag/backend/`.
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Generation Consolidation [checkpoint: ]
Delete redundant files and simplify the generation package.

- [ ] Task: Delete `src/render_tag/generation/builder.py`
    - [ ] Confirm no other modules import it.
    - [ ] Permanently delete the file.
- [ ] Task: Remove other redundant generation utilities
    - [ ] Delete any other identified "zombie" files in `src/render_tag/generation/`.
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Final Verification [checkpoint: ]
Ensure the system is clean and fully functional.

- [ ] Task: Run full regression test suite
    - [ ] Execute `uv run pytest` to ensure all functionality remains intact.
- [ ] Task: Verify Import Linter
    - [ ] Run `uv run lint-imports` to ensure no new violations were introduced.
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
