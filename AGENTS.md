# AGENTS.md - The Law and The Loop

Welcome, Agent. This project follows **Google Antigravity Best Practices**. Your goal is to generate high-fidelity synthetic data without breaking the render pipeline.

---

## 1. The Law
These are absolute constraints. Violation leads to failure.

1.  **Strict Isolation**: Logic (`src/render_tag/generator.py`) must NEVER import `bpy`.
2.  **The Subprocess Pattern**: Blender runs in its own process. Interact ONLY via `SceneRecipe` JSON.
3.  **Schema is King**: Validation against `src/render_tag/schema.py` is mandatory.
4.  **UV Only**: All commands must use `uv run`.

> [!IMPORTANT]
> **READ THESE RULES BEFORE ACTING:**
> - [Core Rules](file:///.agent/rules/core.md): The immutable laws and behaviors.
> - [Coding Standards](file:///.agent/rules/coding.md): Typing, testing, and formatting.
> - [Architecture](file:///.agent/rules/architecture.md): Host vs. Backend separation details.
>
> Use [.agent/workflows/](file:///.agent/workflows/) for common tasks.

---

## 2. The Loop (Iterate Fast)
Do not wait for 3D renders. Use the **Shadow Render** loop.

1.  **Draft Logic**: Edit `src/render_tag/generator.py`.
2.  **Generate & Validate**:
    ```bash
    uv run render-tag generate --config configs/dev.yaml --output output/test --scenes 1
    uv run render-tag validate-recipe --recipe output/test/scene_recipes.json
    ```
3.  **Visual Feedback**:
    ```bash
    uv run render-tag viz-recipe --recipe output/test/scene_recipes.json --output output/test/viz
    ```
4.  **Optimize**: Refine math based on 2D PNG outputs.

---

## 3. Workflows
Use these slash commands for standard operations:
- `/lint_code`: Lint and format using `ruff`.
- `/type_check`: Type check using `ty`.
- `/generate_data`: Full generation and validation sequence.

---

## 4. Directory Map
- [schema.py](file:///src/render_tag/schema.py): The source of truth for recipes.
- [generator.py](file:///src/render_tag/generator.py): Procedural math logic.
- [blender_main.py](file:///src/render_tag/scripts/blender_main.py): 3D render driver.
- [.agent/](file:///.agent/): Agent-specific rules and workflows.