# Specification - Test Suite Optimization

## Overview
As the project grows, the reliance on Blender-based integration tests significantly slows down the development cycle. This track optimizes the test suite by strictly separating slow integration tests from fast unit tests and expanding the "Shadow Render" (skip-render) logic to catch earlier in the pipeline without the overhead of full 3D rendering.

## Functional Requirements
- **Test Separation:**
    - Reorganize the `tests/` directory to separate `unit/` and `integration/` tests.
    - Implement a `pytest` marking system (`@pytest.mark.slow` or `@pytest.mark.integration`) to allow running fast tests by default.
- **Enhanced Fast Path Validation:**
    - Extend the `generate --skip-render` workflow to perform comprehensive "pre-flight" checks.
    - **Asset Validation:** Verify all referenced texture and HDRI paths exist before attempting a render.
    - **Geometric Validation:** Implement fast 2D geometry checks to detect overlapping tags or markers placed outside the floor boundaries.
    - **Visibility Heuristics:** Approximate camera frustum checks in pure Python to warn if a camera is likely looking away from all markers.
- **Workflow Integration:**
    - Update the project `README.md` or developer guides with instructions on how to run fast vs. full test suites.

## Non-Functional Requirements
- **Target Execution Time:** Fast test suite (Unit + Skip-Render) should complete in under 10 seconds.
- **Maintainability:** Ensure that validation logic remains in sync with the actual Blender rendering logic to avoid false positives/negatives.

## Acceptance Criteria
- [ ] Pytest configuration allows running `pytest -m "not integration"` to execute only fast tests.
- [ ] Integration tests are moved to a dedicated `tests/integration` folder.
- [ ] `render-tag generate --skip-render` correctly catches and reports missing assets or overlapping geometry.
- [ ] CI pipeline is updated to run the fast suite on every push and the slow suite only on PRs/Main merges.
