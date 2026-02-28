---
description: Generate, validate, and visualize scene recipes (The Loop)
---

# The Shadow Render Loop

This workflow implements the fast iteration loop described in AGENTS.md.

1.  **Generate Scene Recipes**
    Generate recipes from a configuration file.
    ```bash
    uv run render-tag generate --config configs/default.yaml --output output/dev --scenes 5
    ```

2.  **Validate Recipes**
    Ensure the generated recipes adhere to the schema.
    ```bash
    uv run render-tag validate-recipe --recipe output/dev/scene_recipes.json
    ```

3.  **Visualize (Shadow Render)**
    Create 2D visualizations of the recipes to verify logic without full 3D rendering.
    ```bash
    uv run render-tag viz recipe --recipe output/dev/scene_recipes.json --output output/dev/viz
    ```

4.  **Reflect**
    Check `output/dev/viz` for the generated images. If the geometry or placement looks wrong, adjust `src/render_tag/generator.py` and repeat.