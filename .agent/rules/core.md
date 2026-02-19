---
trigger: always_on
---

# Core Rules & Directives

## The Law (Immutable Constraints)
These constraints are absolute. Violation leads to immediate failure.

1.  **Strict Isolation**: `src/render_tag/generator.py` (Logic) and `src/render_tag/schema.py` must NEVER import `bpy` (Blender API) or `blenderproc`. These libraries do not exist in the host environment.
2.  **The Subprocess Pattern**: Blender runs in its own process. You interact with it ONLY via `SceneRecipe` JSON files.
3.  **Schema is King**: If it doesn't validate against `src/render_tag/schema.py`, it doesn't exist.
4.  **UV Only**: All package management and command execution must use `uv`. NEVER use `pip` or `conda` directly.
5.  **Gitignored Outputs**: All temporary data, logs, debug artifacts, and generated datasets MUST be saved to gitignored directories (e.g., `output/`, `tmp/`, or `fast_output/`). NEVER commit generated data to the repository.

## Agent Behaviors
1.  **Explain Before Acting**: Always provide a one-sentence explanation before running shell commands or editing files.
2.  **Verify First**: Read files and check the environment before making assumptions.
3.  **Iterative Development**: Use the "Shadow Render" loop (Generate -> Validate -> Visualize) to iterate fast without waiting for full 3D renders.