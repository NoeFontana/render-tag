# Implementation Plan: Test Suite Optimization

## Phase 1: Consolidation & Organization
- [ ] Task: Merge `tests/unit/cli/test_cli_validation.py` into `tests/unit/cli/test_cli_commands.py` or a new unified CLI test.
- [ ] Task: Reorganize `tests/unit/` to separate "Math/Core" (fast) from "Blender/Backend" (heavy).
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Consolidation & Organization' (Protocol in workflow.md)

## Phase 2: Performance & Mocking
- [ ] Task: Review `tests/integration/test_integration.py` and optimize slow shard invariance tests.
- [ ] Task: Mock BlenderProc/Blender where possible in "Backend" unit tests to avoid subprocess overhead.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Performance & Mocking' (Protocol in workflow.md)

## Phase 3: Stability & Final Polish
- [ ] Task: Stabilize `test_hot_loop_render_command` (ensure no port/file race conditions).
- [ ] Task: Run final benchmark of test durations.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Stability & Final Polish' (Protocol in workflow.md)
