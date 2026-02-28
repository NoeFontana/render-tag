# Specification: Automated CI Quality Gates (GitHub Actions)

## Overview
Implement a modern GitHub Actions CI workflow for the `render-tag` repository. This track will enforce high code quality standards, architectural integrity, and functional correctness through automated gates on every push and pull request. By leveraging `uv` and `astral-sh/setup-uv`, the pipeline will ensure extremely fast and deterministic execution.

## Functional Requirements
- **Automated Formatting Check:** Enforce consistent style using `ruff format`.
- **Linting & Quality Gates:** Run `ruff check` to identify code smells and PEP violations.
- **Architectural Enforcement:** Execute `uv run lint-imports` to strictly maintain the boundary between host logic and the rendering backend.
- **Static Type Checking:** Run `ty` (per project tech stack) to verify type safety across the `src/` and `tests/` directories.
- **Configuration Validation:** Execute `render-tag validate-config` to ensure default YAML files are functionally sound.
- **Parallel Test Suite:** Run the full `pytest` suite in parallel using `pytest-xdist` to catch regressions rapidly.
- **Dependency Isolation:** Use `uv` to manage a clean, cached, and isolated virtual environment for every CI run.

## Non-Functional Requirements
- **Execution Speed:** Utilize `astral-sh/setup-uv` for aggressive dependency caching.
- **Deterministic Runs:** Pin dependencies via `uv.lock` and project-level `pyproject.toml`.
- **Environment Parity:** Ensure the CI environment (Ubuntu) matches the developer toolchain.

## Acceptance Criteria
- [ ] A new workflow file `.github/workflows/ci.yml` is successfully created.
- [ ] All defined quality gates (formatting, linting, typing, architectural checks) pass in the CI environment.
- [ ] The full parallel test suite passes within the CI pipeline.
- [ ] Configuration validation check succeeds using the project's default settings.
- [ ] The workflow successfully caches and restores `uv` dependencies to optimize run times.

## Out of Scope
- **GPU-Accelerated Rendering:** CI tests will remain mock-based; no actual Blender rendering on GPU-enabled runners is required for this track.
- **Hugging Face Token Management:** All quality gates will use mocked assets; no `HF_TOKEN` will be integrated in this initial phase.
- **Automatic Releases:** This track focuses on validation gates, not deployment or release automation.
