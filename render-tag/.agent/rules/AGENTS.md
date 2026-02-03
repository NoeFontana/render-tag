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

2.  **Recipe Contract**:
    -   Do not pass complex Python objects to the backend. Use the `SceneRecipe` JSON schema defined in `src/render_tag/schema.py`.
