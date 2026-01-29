# AGENTS.md - The Law and The Loop

**If you are an AI Agent reading this:**
Welcome. This codebase has been optimized for YOU.
Follow these rules to succeed efficiently without getting stuck in dependency hell or broken render loops.

---

## 1. The Law

1.  **Do NOT import `bpy` in Logic Code.**
    - `generator.py` and pure-Python logic must NEVER import Blender's `bpy`.
    - If you are writing scene generation logic, use `src/render_tag/schema.py` and standard math libraries.
    - Blender dependencies live ONLY in `src/render_tag/scripts/executor.py` and `blender_main.py`.

2.  **Use the Recipe Pattern.**
    - **Input**: Config (YAML) -> **Logic**: Generator (Python) -> **Output**: Recipe (JSON).
    - Your goal is to produce a valid `scene_recipes.json`.
    - Do not try to write scripts that "drive" Blender directly nicely. Just output data.

3.  **Strict Schema Compliance.**
    - All recipes must validate against `SceneRecipe` in `src/render_tag/schema.py`.
    - Use `uv run render-tag validate-recipe` to check your work.

---

## 2. The Loop (How to Iterate Fast)

**Do NOT run the full Blender render to test layout changes.** It is slow and opaque.
Use this feedback loop instead:

1.  **Modify Logic**: Edit `generator.py` or your layout script.
2.  **Generate Recipe**:
    ```bash
    uv run render-tag generate --config configs/your_config.yaml --output output/test --scenes 1
    # Arguments automatically trigger recipe generation
    ```
3.  **Validate**:
    ```bash
    uv run render-tag validate-recipe --recipe output/test/scene_recipes.json
    ```
    - If this fails, FIX IT. Do not proceed.
4.  **Visualize (Shadow Render)**:
    ```bash
    uv run render-tag viz-recipe --recipe output/test/scene_recipes.json --output output/test/viz
    ```
    - Check the PNGs in `output/test/viz`. Are the tags overlapping? Is the board where you expect?
5.  **Render (Only when sure)**:
    ```bash
    # The 'generate' command runs this automatically if validation passes (conceptually),
    # or you can run the full generation command again.
    uv run render-tag generate ... 
    ```

---

## 3. The Architecture

```text
[User Config (YAML)]
       |
       v
+-----------------------+
|   Logic Engine        |  <-- YOU WORK HERE
| (src/render_tag/generator.py) |
| (Pure Python, Fast)   |
+-----------------------+
       |
       v
[Scene Recipe (JSON)]   <-- The Interface (Schema)
       |
    +--+------------------+
    |                     |
    v                     v
+------------+      +------------+
| Validator  |      | Visualizer |
| (fast)     |      | (fast 2D)  |
+------------+      +------------+
    |                     |
    | (Approved)          v
    v               [PNG Feedback]
+-----------------------+
|   Blender Executor    |  <-- Opaque Box
| (runs inside Blender) |
+-----------------------+
       |
       v
    [Pixels]
```

## 4. Key Files

- **Contract**: `src/render_tag/schema.py` (Read this to understand the JSON structure)
- **Logic**: `src/render_tag/generator.py` (Where the math happens)
- **Executor**: `src/render_tag/scripts/executor.py` (The Blender driver - don't touch unless adding new object types)
- **Tools**: `src/render_tag/tools/` (Validator, Visualizer)
