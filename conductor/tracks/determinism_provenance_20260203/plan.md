# Implementation Plan - Determinism & Provenance

This plan implements a strict deterministic seed hierarchy and a sidecar metadata provenance system to ensure scientific reproducibility of generated datasets.

## Phase 1: Deterministic Seed Hierarchy
**Goal:** Implement a stable derivation of shard and scene seeds from a single master seed.

- [x] Task: Implement `SeedManager` utility 6a91802
    - [ ] Create a utility class in `src/render_tag/common/math.py` to handle sequential seed derivation.
    - [ ] Write tests verifying that `SeedManager(master_seed).get_shard_seed(n)` is stable and repeatable.
- [ ] Task: Integrate `SeedManager` into Sharding Logic
    - [ ] Update `src/render_tag/orchestration/sharding.py` to use `SeedManager` for assigning seeds to shards.
    - [ ] Ensure the shard seed is passed as an environment variable or argument to the Blender subprocess.
- [ ] Task: Scene-Level Determinism
    - [ ] Update `src/render_tag/generator.py` to initialize its local random state using the provided shard/scene seed.
    - [ ] Verify that generating 10 `SceneRecipes` with the same shard seed produces identical JSON output.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Deterministic Seed Hierarchy' (Protocol in workflow.md)

## Phase 2: Metadata Provenance System
**Goal:** Automatically generate and save sidecar JSON files containing full generation context for every image.

- [ ] Task: Git Hash Retrieval Utility
    - [ ] Implement a helper to retrieve the current HEAD git hash.
    - [ ] Write tests ensuring it handles cases where `.git` is missing or the repo is dirty.
- [ ] Task: Update Sidecar Schema
    - [ ] Extend `src/render_tag/schema.py` to include a `SceneProvenance` model (git_hash, timestamp, recipe_snapshot).
- [ ] Task: Implement Sidecar Writer
    - [ ] Update `src/render_tag/data_io/writers.py` to write the `scene_xxxx_meta.json` file alongside the PNG.
    - [ ] Ensure the sidecar is written by the backend (`blender_main.py`) or the orchestration layer after a successful render.
- [ ] Task: Integration Test - Provenance Chain
    - [ ] Create an integration test that runs a single scene render and verifies the existence and content of the sidecar JSON.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Metadata Provenance System' (Protocol in workflow.md)

## Phase 3: Verification & Benchmarking
**Goal:** Verify bit-identical reproducibility and assess performance overhead.

- [ ] Task: Reproducibility Benchmark Test
    - [ ] Write a script that runs the same job twice and compares the resulting images and sidecars for equality.
- [ ] Task: Verify Shard-Invariance
    - [ ] Verify that running a 10-scene job with 1 shard vs. 2 shards produces the same 10 images.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Verification & Benchmarking' (Protocol in workflow.md)
