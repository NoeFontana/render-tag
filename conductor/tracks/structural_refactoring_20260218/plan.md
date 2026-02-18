# Implementation Plan: Structural Refactoring

## Phase 1: High-Priority Decomposition
- [ ] Task: Refactor `SceneCompiler._build_recipe` (Complexity: 22).
- [ ] Task: Refactor `UnifiedWorkerOrchestrator.release_worker` (Complexity: 12).
- [ ] Task: Refactor `UnifiedWorkerOrchestrator.orchestrate` (Complexity: 17).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: High-Priority Decomposition' (Protocol in workflow.md)

## Phase 2: CLI & Backend Logic
- [ ] Task: Refactor `execute_recipe` in `engine.py` (Complexity: 11).
- [ ] Task: Refactor `generate_board_records` in `projection.py` (Complexity: 16).
- [ ] Task: Refactor `visualize_dataset` in `visualization.py` (Complexity: 19).
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI & Backend Logic' (Protocol in workflow.md)

## Phase 3: Verification & Polish
- [ ] Task: Run full test suite and verify no regressions.
- [ ] Task: Run final cyclomatic complexity check to confirm improvements.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Verification & Polish' (Protocol in workflow.md)
