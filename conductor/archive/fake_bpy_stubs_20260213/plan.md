# Implementation Plan: Static Type Stubs for Blender API (fake-bpy)

Implement high-fidelity type stubs for Blender modules to enable robust static analysis and autocompletion, replacing legacy manual mocks.

## Phase 1: Dependency & Environment Setup
- [x] Task: Add `fake-bpy-module-4.2` to the `dev` dependency group in `pyproject.toml` and sync.
- [~] Task: Verify that `import bpy` and `import mathutils` are discoverable by the local interpreter.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Dependency & Environment Setup' (Protocol in workflow.md)

## Phase 2: Codebase Purification (Refactoring)
- [x] Task: Locate and delete all manual Blender mock implementations (e.g., `MockBPY`).
- [x] Task: Remove `# type: ignore` comments related to Blender API usage.
- [x] Task: Simplify `TYPE_CHECKING` blocks for Blender modules (allowing direct imports in backend code).
- [x] Task: Conductor - User Manual Verification 'Phase 2: Codebase Purification' (Protocol in workflow.md)

## Phase 3: Integration & Finalization
- [x] Task: Execute the project type checker (`uv run ty`) and resolve any newly discovered type errors in backend modules.
- [x] Task: Verify autocompletion for core types like `bpy.types.Object` and `mathutils.Vector`.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Integration & Finalization' (Protocol in workflow.md)

## Phase: Review Fixes
- [x] Task: Apply review suggestions 8361e2f
