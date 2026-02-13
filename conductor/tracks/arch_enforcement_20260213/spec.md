# Specification: Architectural Boundary Enforcement (Split-Brain)

## Overview
Implement a strict architectural linter to enforce the "Split-Brain" design of the `render-tag` codebase. This ensures that pure Python modules (orchestration and common) remain isolated from Blender-specific modules and dependencies (`bpy`, `render_tag.backend`).

## Goals
- Prevent accidental leakage of Blender dependencies into the orchestration layer.
- Formalize the architectural contract between the Host (Pure Python) and Backend (Blender Python).
- Provide a clear, automated mechanism for developers to verify architectural integrity.

## Functional Requirements
1.  **Dependency Enforcement**:
    -   `src/render_tag/orchestration/` MUST NOT import `bpy` or `render_tag.backend`.
    -   `src/render_tag/common/` MUST NOT import `bpy` or `render_tag.backend`.
2.  **Tooling**:
    -   Utilize `import-linter` to define and enforce these contracts.
    -   Create a configuration file (e.g., `.importlinter` or within `pyproject.toml`) specifying the "Forbidden Modules" and "Layers" contracts.
3.  **CLI Integration**:
    -   Expose the check via a new command: `uv run render-tag lint-arch`.
    -   The command must return a non-zero exit code on violation and print a detailed report of the offending imports and their paths.
4.  **Workflow Integration**:
    -   Update `.agent/workflows/lint_code.md` to include the architectural linting step.

## Non-Functional Requirements
- **Performance**: The architectural check should execute in less than 5 seconds on a standard developer machine.
- **Maintainability**: The configuration should be declarative and easy to update as new modules are added.

## Acceptance Criteria
- [ ] `import-linter` is added as a development dependency.
- [ ] Architectural contracts are defined for `orchestration` and `common`.
- [ ] `uv run render-tag lint-arch` correctly identifies and reports violations (verified with a temporary "poison" import).
- [ ] `uv run render-tag lint-arch` returns exit code 0 on the current clean codebase.
- [ ] The command is integrated into the project's standard linting workflow.

## Out of Scope
- Enforcement of circular dependencies within the `backend` or `orchestration` sub-packages themselves.
- Enforcing import boundaries for third-party libraries other than `bpy` (unless they are specifically identified as "backend-only").
