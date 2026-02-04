# Specification - Determinism & Provenance (The "Science" Layer)

## Overview
In scientific computing, reproducibility is paramount. This track implements a strict deterministic generation pipeline and a robust provenance system. It ensures that any image in a dataset can be perfectly reproduced if provided with the same configuration and seed, and that every image carries its own complete generation history.

## Functional Requirements
- **Deterministic Seed Hierarchy:**
    - The "Master Seed" in the global configuration must generate deterministic "Shard Seeds" for parallel execution.
    - Shard Seeds will be derived using a **Sequential Sequence**: the Master Seed initializes a primary RNG, and Shard `N` is assigned the `N`-th value in its sequence.
    - Individual scene objects (tag placement, camera pose, lighting) must be derived from the Shard Seed in a stable, ordered manner.
- **Sidecar Metadata Provenance:**
    - Every generated image file (e.g., `scene_0001.png`) must be accompanied by a sidecar JSON file (e.g., `scene_0001_meta.json`).
    - The sidecar MUST contain:
        - The full `SceneRecipe` used for that specific image.
        - The global seed and the specific seed used for that scene.
        - The Git commit hash of the `render-tag` repository at the time of generation.
        - Timestamps for generation and rendering.

## Non-Functional Requirements
- **Architecture Independence (Best Effort):** The pipeline should aim to produce identical results across different machines, recognizing that underlying library versions (OpenCV, Blender) or hardware (CPU vs GPU) may introduce minor floating-point variations.
- **Minimal Overhead:** Sidecar generation should not significantly increase total dataset generation time.

## Acceptance Criteria
- [ ] Running the same configuration (Job ID + Master Seed) twice on the same machine produces bit-identical images.
- [ ] Every image in an output directory has a corresponding sidecar JSON file containing the correct Git hash and full scene parameters.
- [ ] Sharding the same job (e.g., into 2 shards vs 4 shards) results in the same total set of images and metadata when seeds are controlled.

## Out of Scope
- Perfect bit-identical reproducibility across different OS versions or GPU architectures (where floating-point math differs).
