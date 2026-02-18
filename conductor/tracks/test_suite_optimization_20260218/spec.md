# Specification: Test Suite Optimization

## Overview
Improve the quality and performance of the test suite by reducing redundancy, optimizing slow tests, and stabilizing flaky components. This ensures a faster and more reliable feedback loop for developers.

## Functional Requirements
1.  **Reduce Redundancy:**
    -   Merge overlapping tests in `tests/unit/cli/`.
    -   Consolidate redundant validation tests.
2.  **Improve Performance:**
    -   Optimize integration tests by using smaller batches or more targeted mocks.
    -   Identify and mock heavy dependencies in unit tests that are currently running subprocesses.
3.  **Refactor Flaky Tests:**
    -   Fix `test_hot_loop_render_command` instability.
    -   Ensure consistent behavior in parallel test execution.
4.  **Improve Organization:**
    -   Categorize tests better (e.g., separating pure math tests from Blender-dependent tests).

## Acceptance Criteria
-   Total test execution time is reduced by at least 20%.
-   Redundant test files are merged or removed.
-   All tests pass consistently in parallel (`-n4`).
