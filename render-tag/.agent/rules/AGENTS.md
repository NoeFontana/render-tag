# Agent Rules

Always maintain high code quality and respect the system architecture.

## Code Quality

1.  **Lint and Format**: Before finishing, run:
    ```bash
    # Run workflow: /lint_code
    ```
2.  **Type Check**:
    ```bash
    # Run workflow: /type_check
    ```

## Architecture Constraints

1.  **Host vs Backend Separation**:
    -   **Host Code** (`src/render_tag/` root): NEVER import `bpy`, `blenderproc`, or `mathutils`. These modules do not exist in the standard Python environment.
    -   **Backend Code** (`src/render_tag/backend/`): This code runs INSIDE Blender. It is safe to import `bpy` and `blenderproc`, but wrap them in `try/except ImportError` blocks if the file might be inspected by tools outside Blender (like linters).

3.  **Component Ownership**:
    -   **Parallelism/Sharding**: Addressed in `src/render_tag/orchestration/sharding.py`.
    -   **Data Export/Visualization**: Addressed in `src/render_tag/data_io/`.
    -   **Generation Logic**: Addressed in `src/render_tag/generator.py`.
