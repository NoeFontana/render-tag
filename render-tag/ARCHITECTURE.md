# System Architecture

`render-tag` is designed as a **Host-Backend** system to bridge the gap between a standard Python environment and Blender's embedded Python environment.

## High-Level Overview

1.  **Host Process (Standard Python)**:
    *   **CLI (`cli.py`)**: Entry point for users. Handles configuration validation and orchestration.
    *   **Generator (`generator.py`)**: Pure logic component. detailed "Recipes" (`SceneRecipe`) for each scene based on the configuration. It is deterministic and has NO dependency on Blender.
    *   **Output**: The Host process produces a `scene_recipes.json` file, which acts as the contract between Host and Backend.

2.  **Backend Process (Blender)**:
    *   **Executor (`backend/executor.py`)**: The entry point running inside Blender. It loads `scene_recipes.json` and blindly executes the instructions.
    *   **BlenderProc**: Used by the executor for low-level interaction with Blender (rendering, object creation).

## Directory Structure

```
src/render_tag/
├── cli.py              # Host: CLI entry point
├── config.py           # Host: Configuration schema
├── generator.py        # Host: Logic to create recipes
├── schema.py           # Shared: Data contracts (Recipes)
├── geometry/           # Shared: Pure math/geometry logic
├── backend/            # Backend: Code running INSIDE Blender
│   ├── executor.py     #   - Main driver
│   ├── scene.py        #   - Scene setup (lights, background)
│   ├── assets.py       #   - Asset loading (tags, textures)
│   └── projection.py   #   - 3D to 2D projection logic
└── tools/              # Utilities
```

## The "Recipe" Contract

The communication between Host and Backend is one-way via the `SceneRecipe` schema.

-   **Host** decides *what* to render (positions, camera angles, lighting parameters).
-   **Backend** decides *how* to render it (Blender API calls).

This separation allows us to:
1.  Debug logic without opening Blender.
2.  Run unit tests on layout generation easily.
3.  Swap out the backend (e.g., to a different renderer) if needed in the future, as long as it adheres to the Recipe contract.
