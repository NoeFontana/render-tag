# Implementation Plan: Test Suite Optimization

## Phase 1: Consolidation & Organization
- [x] Task: Merge `tests/unit/cli/test_cli_validation.py` into `tests/unit/cli/test_cli_commands.py` or a new unified CLI test.
- [x] Task: Reorganize `tests/unit/` to separate "Math/Core" (fast) from "Blender/Backend" (heavy).
- [x] Task: Conductor - User Manual Verification 'Phase 1: Consolidation & Organization' (Protocol in workflow.md)

## Phase 2: Performance & Mocking
- [x] Task: Review `tests/integration/test_integration.py` and optimize slow shard invariance tests.
- [x] Task: Mock BlenderProc/Blender where possible in "Backend" unit tests to avoid subprocess overhead.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Performance & Mocking' (Protocol in workflow.md)

## Phase 3: Stability & Final Polish
- [x] Task: Stabilize `test_hot_loop_render_command` (ensure no port/file race conditions).
- [x] Task: Run final benchmark of test durations.
- [x] Task: Staff Engineer - Fix critical session-killing bug in `PersistentWorkerProcess.stop` (safety check for `os.killpg(0)`).
- [x] Task: Staff Engineer - Standardize `Command` and `Response` schemas across all tests (fix Pydantic `ValidationError`s).
- [x] Task: Conductor - User Manual Verification 'Phase 3: Stability & Final Polish' (Protocol in workflow.md)
