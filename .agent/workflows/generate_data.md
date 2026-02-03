---
description: generate and validate scene recipes
---

1. Generate scene recipes from config
   ```bash
   uv run render-tag generate --config configs/random_tags.yaml --output output/dev --scenes 5
   ```

2. Validate the generated recipes
   ```bash
   uv run render-tag validate-recipe --recipe output/dev/scene_recipes.json
   ```

3. Visualize for feedback
   ```bash
   uv run render-tag viz-recipe --recipe output/dev/scene_recipes.json --output output/dev/viz
   ```
