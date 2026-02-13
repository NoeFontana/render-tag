# Specification: Blender Environment Bootstrap Pattern

## Overview
Implement a robust "Bootstrap Pattern" to synchronize the Blender Python environment with the project's virtual environment. This replaces brittle `sys.path` manipulation with an environment-aware initialization module, ensuring that Blender has access to all project dependencies (Pydantic, etc.) and the live `src/` code.

## Goals
- Eliminate "script-kiddie" `sys.path` hacks across backend scripts.
- Ensure pixel-perfect dependency parity between the Host (orchestrator) and Backend (Blender).
- Support seamless development in both headless CLI mode and the Blender GUI.
- Implement "Fail Fast" logic to detect environment mismatch early.

## Functional Requirements
1.  **Bootstrap Module (`src/render_tag/backend/bootstrap.py`)**:
    -   Must be the first import in any Blender-side entry point.
    -   Use `site.addsitedir()` to process `.pth` files (supporting `uv` editable installs).
    -   **Orchestration Mode**: Prioritize the site-packages path provided via `RENDER_TAG_VENV_SITE_PACKAGES` env var.
    -   **Dev Mode Fallback**: If the env var is missing, search parent directories for `pyproject.toml` to locate the local `.venv`.
    -   **Path Precedence**: Ensure the project `src/` directory is at the front of `sys.path` to prioritize live code changes.
2.  **Orchestration Handshake**:
    -   Update `src/render_tag/orchestration/executors.py` to detect the current venv's site-packages.
    -   Inject this path into the subprocess environment as `RENDER_TAG_VENV_SITE_PACKAGES`.
    -   Set `PYTHONNOUSERSITE=1` to ensure strict isolation from system-wide Python packages.
3.  **Entry Point Refactoring**:
    -   Refactor `src/render_tag/backend/render_loop.py`, `src/render_tag/scripts/blender_main.py` (if it exists), and other backend scripts to use the bootstrap module.
    -   Remove existing manual `sys.path.append` logic.
4.  **Validation (Fail Fast)**:
    -   The bootstrap module must verify the presence of critical dependencies (e.g., `pydantic`).
    -   Raise a descriptive `RuntimeError` if the environment cannot be initialized.

## Non-Functional Requirements
- **Observability**: Silent by default; initialization logs should only appear on failure or if a debug flag is enabled.
- **Performance**: Environment discovery and injection should add negligible overhead (<100ms) to the startup time.

## Acceptance Criteria
- [ ] `bootstrap.py` is implemented and handles both orchestrated and manual discovery.
- [ ] Orchestrator correctly passes the venv path to Blender subprocesses.
- [ ] Manual `sys.path` hacks are removed from the backend codebase.
- [ ] `uv run render-tag generate` (or equivalent) passes successfully using the new bootstrap.
- [ ] Opening a backend script in Blender GUI and calling the bootstrap function works without manual setup.
