# Architecture

`render-tag` follows a strictly decoupled architecture to ensure that generation logic is independent of the rendering engine.

## High-Level Overview

The system is divided into **Host** code (Python >=3.11) and **Backend** code (Blender/BlenderProc).

```mermaid
graph TD
    A["CLI / Python API"] --> B["SceneCompiler"]
    B -- "SceneRecipe" --> C["Unified Orchestrator"]
    C -- "ZMQ REQ" --> D["ZMQ Server (Blender)"]
    D --> E["Worker Server"]
    E --> F["BlenderBridge"]
    F --> G["BlenderProc / Blender"]
    G --> H["Rendered Images & Metadata"]
```

## Components

### 1. Core (`src/render_tag/core/`)
The foundation of the system. Contains the single source of truth **Schemas** (Pydantic models), configuration logic, and fundamental utilities.

### 2. Generation (`src/render_tag/generation/`)
Pure Python procedural logic. Samples parameters and builds `SceneRecipe` objects. It has **no** dependency on Blender.

### 3. Backend (`src/render_tag/backend/`)
The 3D rendering engine.

- **`bootstrap.py`**: Centralized environment stabilization. Handles paths, venv site-packages, and logging.
- **`bridge.py`**: `BlenderBridge` provides explicit Dependency Injection for Blender/BlenderProc APIs.
- **`worker_server.py`**: Implementation of the "Hot Loop" ZMQ server.
- **`engine.py`**: The actual BlenderProc execution logic.

### 4. Orchestration (`src/render_tag/orchestration/`)
The `UnifiedWorkerOrchestrator` manages the lifecycle of `PersistentWorkerProcess` instances. It handles ZMQ communication, VRAM guardrails, and parallel sharding.

### 5. Data I/O (`src/render_tag/data_io/`)
Handles asset loading, caching, and writing final annotations (COCO, CSV).

## The "Hot Loop" (Persistent Workers)

To avoid the significant overhead of starting Blender for every scene, `render-tag` uses a persistent worker architecture.

1.  **Orchestrator** starts one or more Blender instances in the background.
2.  Each Blender instance runs a **ZMQ Server** (`zmq_server.py`).
3.  The Orchestrator sends **Scene Recipes** over ZMQ.
4.  The **Worker Server** receives the recipe, uses the **BlenderBridge** to access APIs, and renders the scene.
5.  Blender remains ready for the next recipe without quitting.

This "Hot Loop" can improve rendering throughput by $2-5\times$ for small scenes.

## Rendering Performance (CV-Safe)

To maximize generation speed while maintaining the high sub-pixel accuracy required for fiducial tag detection, `render-tag` employs several optimization strategies:

### 1. Adaptive Sampling & Denoising
We use Cycles' **Adaptive Sampling** with a noise threshold (default $0.05$) rather than a fixed sample count. This is combined with **Intel OpenImageDenoise (OIDN)** guided by Albedo and Normal passes. This "CV-Safe" approach ensures that flat surfaces render nearly instantaneously while high-frequency edges (like tag corners) receive enough samples to remain sharp and accurate.

### 2. Light Path Optimization

Standard path tracing bounces light many times to achieve artistic realism. For computer vision training, we "min-max" these bounces to balance fidelity with throughput:

| Parameter | Value | Rationale |
| :--- | :---: | :--- |
| **Total Bounces** | 4 | Diminishing returns for CV after 4. |
| **Diffuse** | 2 | Enough for realistic indirect lighting. |
| **Glossy** | 4 | Critical for preserving specular highlights (glare). |
| **Transmission** | 0 | Disabled unless glass/refraction is explicitly needed. |
| **Caustics** | Off | Computationally expensive and irrelevant for tag detection. |

## Geometric Data Contract (3D-Anchored Orientation)

To ensure synthetic data maintains 6DoF orientation integrity ($\text{roll}, \text{pitch}, \text{yaw}$), `render-tag` follows a strict local-space geometric contract for all point-based subjects (Tags, Boards).

### The "Logical Corner 0" Rule

All subject keypoint arrays MUST be ordered such that:

1.  **Index 0**: Represents the **Logical Top-Left** of the subject's local payload/texture, located at local coordinates $(-w/2, -h/2, 0)$.
2.  **Indices 1, 2, 3**: Follow a strict **Clockwise (CW)** winding in the subject's local $XY$ plane.
    -   Index 1: Logical Top-Right $(+w/2, -h/2, 0)$
    -   Index 2: Logical Bottom-Right $(+w/2, +h/2, 0)$
    -   Index 3: Logical Bottom-Left $(-w/2, +h/2, 0)$

### Architectural Enforcement

-   **Asset Layer**: `keypoints_3d` are assigned explicitly in local coordinates during mesh generation.
-   **Projection Layer**: Performs a pure mathematical transformation from world space $P_{world}$ to pixel space $p_{pixel}$:

    $$
    p_{pixel} = K [R|t] P_{world}
    $$

    This ensures zero-drift between the 3D asset and its 2D annotations without any visual re-sorting heuristics.

-   **Annotation Layer**: Preserves the original 3D indices in the 2D output (COCO keypoints, CSV corners).

## Data Products: `rich_truth.json`

The `rich_truth.json` file is the canonical "Data Product" for a rendered dataset. It exists in two wire formats — the reader layer (`unwrap_rich_truth`) handles both transparently.

### v1 — Legacy (bare array)

```json
[
  { "image_id": "frame_0001", "tag_id": 0, "corners": [[x,y], ...], ... },
  ...
]
```

Produced by pipelines without an `eval_margin_px` setting. `corners_visibility` and `keypoints_visibility` are absent (null in `DetectionRecord`).

### v2 — Versioned envelope

```json
{
  "version": "2.0",
  "evaluation_context": {
    "photometric_margin_px": 21,
    "truncation_policy": "ternary_visibility"
  },
  "records": [
    {
      "image_id": "frame_0001",
      "tag_id": 0,
      "corners": [[x,y], ...],
      "corners_visibility": [2, 1, 2, 2],
      "keypoints_visibility": [2, 2, 1, ...],
      ...
    }
  ]
}
```

Produced when `camera.eval_margin_px > 0` in the config. The `evaluation_context` header is informational; the per-record `eval_margin_px` field is the authoritative source for which margin was applied to each detection.

### `KeypointVisibility` Convention

Per-keypoint visibility follows the COCO keypoint convention extended with a semantic "Don't Care" state:

| Value | Name | Meaning | COCO `v` |
|------:|:-----|:--------|:---------|
| 0 | `OUT_OF_FRAME` | Sentinel `(-1,-1)` — behind camera or not projected | `v=0` (zeroed coords) |
| 1 | `MARGIN_TRUNCATED` | Inside image but within `eval_margin_px` of any edge — excluded from evaluation | `v=1` |
| 2 | `VISIBLE` | Inside the inner safe region — fully evaluable | `v=2` |

`eval_margin_px` is configured per-camera in `camera.eval_margin_px` (YAML) / `CameraConfig.eval_margin_px` (Python). Set to `0` (default) to disable. Recommended value: **5 px** (half-radius of a standard 11-px Gaussian kernel, ensuring corner localization doesn't pick up out-of-image signal).

### `eval_complete` — Partial Detection Filter

A tag or board where *any* corner/keypoint falls inside `eval_margin_px` (or is out-of-frame) sets `eval_complete = false` on the record. This is the canonical field for downstream consumers to exclude partial detections from metrics — no iteration over per-point arrays needed.

```python
# Example: filter rich_truth records for clean evaluation
usable = [r for r in records if r.get("eval_complete", True)]
```

Only meaningful for **TAG records**. A tag with three corners well inside the safe region and one corner just inside the margin zone will have `eval_complete = false`, even though the majority of its geometry is evaluable.

**BOARD records do not use `eval_complete`.** A board can span dozens of saddle points and may legitimately be partially off-screen; a single boolean rollup is not useful. Use `keypoints_visibility` directly to filter individual saddle points:

```python
usable_saddles = [
    pt for pt, v in zip(record["keypoints"], record["keypoints_visibility"])
    if v == 2  # KeypointVisibility.VISIBLE
]
```

For datasets generated without `eval_margin_px` (v1 or `eval_margin_px=0`), `eval_complete` defaults to `true` — backward compatible.

### FiftyOne Views

| Saved view | Filter |
|:---|:---|
| **Evaluation Ready** | `filter_labels(..., F("visibility") == 2)` — per-point; removes individual margin-zone points |
| **Strict Geometry** | No filter — all projected points including margin-zone ones |

Note: the FiftyOne views filter at the *keypoint* level; `eval_complete` filters at the *record* level. Use the saved views for visual inspection and `eval_complete` for programmatic metric gating.

## Reproducibility

Correctness in synthetic data requires strict reproducibility. `render-tag` ensures this through:

- **Environment Fingerprinting:** We hash the `uv.lock` and record the Blender version. If the environment changes, the system issues a warning or error.
- **Config Hashing:** Every dataset contains a `job.json` (JobSpec) that includes a SHA256 hash of the exact configuration used.
- **Asset Hashing:** The `JobSpec` includes a SHA256 hash of all external assets (HDRIs, floor textures, tag images) referenced by the job. This prevents "silent" dataset drift when binary assets are updated on disk or on the Hub.
- **Deterministic Sharding:** Seeds are derived from a master seed and shard index, ensuring that scene #500 is identical regardless of whether it was rendered in a single batch or as part of a specific shard.
