# Specification: Static Type Stubs for Blender API (fake-bpy)

## Overview
Implement static type stubs for the Blender Python API (`bpy`, `mathutils`, etc.) using `fake-bpy-module`. This replaces dangerous manual mocks and "ignore" directives with high-fidelity interface definitions, enabling robust autocompletion and static analysis.

## Goals
- Eliminate "Red Squiggly Lines" in IDEs when working with Blender modules.
- Enable full static type checking for backend modules in CI.
- Modernize the development environment by pinning stubs to the runtime Blender version.
- Purge legacy manual mocks (`MockBPY`) and brittle `TYPE_CHECKING` hacks.

## Functional Requirements
1.  **Dependency Strategy**:
    -   Add `fake-bpy-module-4.2` to the `dev` dependency group in `pyproject.toml`.
    -   Ensure the stubs are strictly isolated from the main `dependencies`.
2.  **Environment Sync**:
    -   Update the local virtual environment (`.venv`) to include the stub packages.
3.  **Codebase Purification**:
    -   Identify and delete all manual Blender mocks (e.g., `MockBPY`, `MagicMock` for `bpy`).
    -   Remove `# type: ignore` comments related to Blender API calls.
    -   Remove `if TYPE_CHECKING: import bpy` guards where possible, as `bpy` will now be discoverable during development.
4.  **Integration**:
    -   Ensure the project's type checker (`ty`/`mypy`) recognizes the stubs.
    -   Configure standard IDEs (VS Code/PyCharm) to use the stubs for autocompletion.

## Non-Functional Requirements
- **Parity**: The stubs must match the Major.Minor version of the Blender runtime used in the production environment (Blender 4.2).
- **Isolation**: The stubs must NOT be imported or used at runtime; they are for static analysis only.

## Acceptance Criteria
- [ ] `fake-bpy-module-4.2` is successfully added to `pyproject.toml`.
- [ ] `uv sync` installs the stubs in the `.venv`.
- [ ] `import bpy` no longer shows errors in the IDE.
- [ ] Autocomplete works for `bpy.context.*` and `mathutils.Vector`.
- [ ] `uv run ty` (or equivalent) passes on backend modules using the new stubs.
- [ ] All manual `MockBPY` implementations are deleted from the repository.

## Out of Scope
- Installing the full Blender binary in the local environment.
- Providing type stubs for non-standard or third-party Blender add-ons.
