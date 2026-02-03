# Contributing to render-tag

Thank you for your interest in contributing to `render-tag`!

## Getting Started

1.  **Install dependencies**:
    ```bash
    uv sync --all-groups
    ```

2.  **Understand the Architecture**:
    Please read [ARCHITECTURE.md](ARCHITECTURE.md) before making changes. The codebase is strictly divided into **Host** (CLI/Generator) and **Backend** (Blender) components.

    -   **Host Code**: `src/render_tag/*.py` (excluding backend). NEVER import `bpy` or `blenderproc` here.
    -   **Backend Code**: `src/render_tag/backend/*.py`. Only this code runs inside Blender.

## Development Workflow

### 1. Make Changes
-   If changing generation logic, modify `src/render_tag/generator.py`.
-   If changing orchestration/sharding, modify `src/render_tag/orchestration/sharding.py`.
-   If changing visualization/I/O, modify `src/render_tag/data_io/`.
-   If changing rendering backend logic, modify `src/render_tag/backend/executor.py`.

### 2. Verify Config
Ensure your changes didn't break config validation:
```bash
uv run render-tag validate-config
```

### 3. Run Tests
```bash
uv run pytest
```

### 4. Lint and Type Check
We strictly enforce code quality:
```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Pull Requests

-   Keep PRs focused on a single feature or fix.
-   Include a plan or description of your changes.
-   Ensure CI passes.
