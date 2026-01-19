# Agent Guide: render-tag

**Project:** `render-tag`
**Goal:** High-fidelity, offline 3D synthetic data generation for AprilTag/ArUco training.
**Consumer:** `locus-tag` (Rust detection engine) & PyTorch training pipelines.

## 🧠 Core Context
This project is a **procedural data generator**. It does *not* perform detection.
It uses **BlenderProc** to create "Golden Datasets"—physically accurate scenes with complex lighting, shadows, and occlusions that cannot be simulated by simple 2D augmentation.

## 🛠 Tech Stack (2026 Standard)
- **Language:** Python 3.12+ (Strict Mode)
- **PackageManager:** `uv` (Fastest Python package installer)
- **Core Engine:** `blenderproc` (Runs via subprocess)
- **CLI:** `typer`
- **Configuration:** `pydantic` (V2) & `yaml`
- **Linting:** `ruff` (Strict)

## 🏗 Architecture: The Subprocess Pattern

Because `blenderproc` runs inside its own bundled Python environment (within Blender), we cannot import it directly into our main CLI. We use a **Driver/Script** separation.

```mermaid
graph LR
    A[CLI (typer)] -->|1. Validates Config| B(Pydantic Model)
    A -->|2. Spawns| C[Subprocess]
    C -->|3. Execs| D[BlenderProc Script]
    D -->|4. Renders| E[Images .jpg]
    D -->|5. Writes| F[Annotations .csv]
1. The Orchestrator (src/render_tag/cli.py)
Role: User interface, config validation, job scheduling.

Dependencies: typer, pydantic, rich.

Action: Serialize config to JSON -> Call blenderproc run ....

2. The Driver (src/render_tag/scripts/blender_main.py)
Role: The actual rendering logic.

Dependencies: blenderproc, numpy.

Action: Load JSON -> Setup Scene -> Physics Drop -> Render -> Save.

📐 Implementation Rules
1. Coordinate Systems & Corner Order (CRITICAL)
Blender: Right-handed, Z-up.

Output Standard:

Order: Clockwise starting from Top-Left.

Sequence: (x1, y1)=TL, (x2, y2)=TR, (x3, y3)=BR, (x4, y4)=BL.

Origin: Top-left of the image is (0,0).

Rule: You must sort the projected 3D vertices to match this order based on the tag's local coordinate system, not just their screen position.

2. Output Formats
The driver must produce TWO label files per batch:

A. Regression CSV (for locus-tag)
Lightweight format for precise corner accuracy testing.

Filename: tags.csv

Columns: image_name, tag_id, c0_x, c0_y, c1_x, c1_y, c2_x, c2_y, c3_x, c3_y

c0: Top-Left

c1: Top-Right

c2: Bottom-Right

c3: Bottom-Left

B. Segmentation/Detection (COCO JSON)
Standard format for training ML models (MaskRCNN, YOLOv8-Seg).

Filename: coco_annotations.json

Content: Standard COCO format including:

segmentation: List of polygon vertices [[x1, y1, x2, y2, ...]] for the tag instance.

bbox: [x, y, width, height]

category_id: Corresponding to the tag family/ID.

🚀 Workflow
Generate: uv run render-tag generate --config configs/hard_shadows.yaml

Debug: uv run render-tag generate --debug ... (Opens Blender UI)


---

### 2. `render-tag/.agent/rules`

```text
# .agent/rules - AI Behavior Guidelines for render-tag

# 1. TOOLING & PACKAGE MANAGEMENT
- ALWAY use `uv` for dependency management.
- NEVER use `pip` directly.

# 2. PYTHON CODING STANDARDS
- STRICT TYPING: Every function signature must have type hints.
- CONFIGURATION: Use `pydantic.BaseModel` for all schemas.

# 3. BLENDERPROC SPECIFIC (STRICT)
- SUBPROCESS AWARENESS:
  - Code in `src/render_tag/scripts/` runs in Blender's internal Python.
  - Use `argparse` to receive JSON config paths.
- CORNER ORDERING:
  - When extracting corners, do NOT rely on `bbox`.
  - You MUST project the object's 3D local vertices `[-1,1,0], [1,1,0], [1,-1,0], [-1,-1,0]` (or equivalent) to 2D.
  - Verify the order is CLOCKWISE (TL -> TR -> BR -> BL) before writing to CSV.
- SEGMENTATION:
  - Use `bproc.writer.write_coco_annotations` for the segmentation masks.
  - Ensure `instance_id` mapping corresponds to the `tag_id`.

# 4. TESTING
- MOCKING: Mock `subprocess.run` for CLI tests.
- SNAPSHOTS: Use `pytest-insta` or similar to snapshot the generated CSV format to ensure column order never drifts.

# 5. DOCUMENTATION
- Docstrings must use Google Style.
- Every Pydantic model field must have a `description="..."`.
