---
description: Lint and format code using Ruff
---

# Lint & Format

Ensure code quality and adherence to style guides.

1.  **Check & Fix**
    Run linter with auto-fix enabled.
    ```bash
    uv run ruff check --fix .
    ```

2.  **Format**
    Apply code formatting.
    ```bash
    uv run ruff format .
    ```

3.  **Architectural Lint**
    Enforce Host/Backend isolation boundaries.
    ```bash
    uv run render-tag lint-arch
    ```