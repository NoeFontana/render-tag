# Implementation Plan: Architectural Boundary Enforcement

Implement a strict architectural linter using `import-linter` to enforce isolation between the Host (Pure Python) and Backend (Blender Python) modules.

## Phase 1: Environment & Tooling Setup
- [x] Task: Install `import-linter` and update dependencies. d0d604a
- [x] Task: Create `import-linter` configuration to define architectural contracts. c68f78e
- [x] Task: Conductor - User Manual Verification 'Phase 1: Environment & Tooling Setup' (Protocol in workflow.md)

## Phase 2: CLI Integration
- [ ] Task: Implement `lint-arch` command in the `render-tag` CLI.
    - [ ] Add `lint_arch` function to the Typer CLI in `src/render_tag/cli/main.py`.
    - [ ] Configure it to invoke `import-linter` via subprocess.
- [ ] Task: Write Tests for CLI command.
    - [ ] Verify `lint-arch` returns 0 on the current codebase.
    - [ ] Verify `lint-arch` returns non-zero when a violation is introduced.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration' (Protocol in workflow.md)

## Phase 3: Workflow Integration & Finalization
- [ ] Task: Update `.agent/workflows/lint_code.md` to include `uv run render-tag lint-arch`.
- [ ] Task: Run full linting suite and verify architectural integrity.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Workflow Integration & Finalization' (Protocol in workflow.md)
