# Implementation Plan - Persistent Data & Scene Recycling ("Hot Loop")

This plan refactors the rendering backend to maintain a persistent state between scenes, significantly reducing overhead and increasing generation throughput.

## Phase 1: Performance Instrumentation ## Phase 1: Performance Instrumentation & Baseline Baseline [checkpoint: 46ee768]
**Goal:** Establish metrics to quantify speedup and ensure no regression in quality.

- [~] Task: Implement Performance Metrics Hook
    - [ ] Create `src/render_tag/tools/benchmarking.py` to track render times and overhead.
    - [ ] Update `executor.py` to log detailed timing data (Blender init, setup, render, export).
- [x] Task: Establish "Cold" Baseline 0264e97
    - [ ] Run a generation of 100 scenes using the current architecture.
    - [ ] Record baseline Mean Time Per Frame (MTPF) and VRAM profile.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Performance Instrumentation' 46ee768 (Protocol in workflow.md)

## Phase 2: Persistent World ## Phase 2: Persistent World & Lazy HDRI Loading Lazy HDRI Loading [checkpoint: f5effbf]
**Goal:** Prevent redundant world state rebuilds and expensive HDRI swaps.

- [~] Task: Write Tests for HDRI Lazy Loader
    - [ ] Create unit tests in `tests/unit/test_backend_world.py` (mocked).
- [x] Task: Implement Persistent World State cc26d29
    - [ ] Refactor `setup_background` in `backend/scene.py` to detect if the requested HDRI is already loaded.
    - [ ] Update `executor.py` to maintain a reference to the active world state.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Persistent World' f5effbf (Protocol in workflow.md)

## Phase 3: Resource Pooling (Tags ## Phase 3: Resource Pooling (Tags & Materials) Materials) [checkpoint: a3bafa2]
**Goal:** Eliminate object creation/deletion overhead and material churn.

- [~] Task: Write Tests for Object Pool
    - [ ] Define expected behavior for pooling (visibility toggling instead of deletion).
- [x] Task: Implement Tag Object Pooling f5effbf
    - [ ] Refactor `create_tag_plane` to retrieve objects from a managed pool in the backend.
    - [ ] Implement a "Reset" function to hide and de-parent unused pool objects.
- [x] Task: Implement Material Slot Recycling f5effbf
    - [ ] Re-use Blender materials by updating image texture nodes in-place rather than creating new materials.
- [x] Task: Implement Hybrid Garbage Collection f5effbf
    - [ ] Add logic to `executor.py` to trigger `orphans_purge` every N scenes.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Resource Pooling' a3bafa2 (Protocol in workflow.md)

## Phase 4: Integration ## Phase 4: Integration & "Hot Loop" Verification "Hot Loop" Verification [checkpoint: 0eb28fe]
**Goal:** Finalize the end-to-end persistent execution and verify speedup.

- [x] Task: Finalize Hot Loop in `executor.py` 1312357
    - [ ] Ensure the main render loop correctly cycles through recipes without teardown.
- [x] Task: Validate Correctness - [ ] Task: Validate Correctness & Benchmarking Benchmarking 17b5e82
    - [ ] Compare "Hot" results against "Cold" baseline for pixel consistency.
    - [ ] Produce final performance report (Cold vs. Hot speedup).
- [x] Task: Run Full Test Suite 0eb28fe
    - [ ] Ensure no regressions in complex scenarios (Industrial, AprilGrid).
- [x] Task: Conductor - User Manual Verification 'Phase 4: Final Integration' 0eb28fe (Protocol in workflow.md)
