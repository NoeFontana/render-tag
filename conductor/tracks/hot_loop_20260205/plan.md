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

## Phase 2: Persistent World & Lazy HDRI Loading
**Goal:** Prevent redundant world state rebuilds and expensive HDRI swaps.

- [ ] Task: Write Tests for HDRI Lazy Loader
    - [ ] Create unit tests in `tests/unit/test_backend_world.py` (mocked).
- [ ] Task: Implement Persistent World State
    - [ ] Refactor `setup_background` in `backend/scene.py` to detect if the requested HDRI is already loaded.
    - [ ] Update `executor.py` to maintain a reference to the active world state.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Persistent World' (Protocol in workflow.md)

## Phase 3: Resource Pooling (Tags & Materials)
**Goal:** Eliminate object creation/deletion overhead and material churn.

- [ ] Task: Write Tests for Object Pool
    - [ ] Define expected behavior for pooling (visibility toggling instead of deletion).
- [ ] Task: Implement Tag Object Pooling
    - [ ] Refactor `create_tag_plane` to retrieve objects from a managed pool in the backend.
    - [ ] Implement a "Reset" function to hide and de-parent unused pool objects.
- [ ] Task: Implement Material Slot Recycling
    - [ ] Re-use Blender materials by updating image texture nodes in-place rather than creating new materials.
- [ ] Task: Implement Hybrid Garbage Collection
    - [ ] Add logic to `executor.py` to trigger `orphans_purge` every N scenes.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Resource Pooling' (Protocol in workflow.md)

## Phase 4: Integration & "Hot Loop" Verification
**Goal:** Finalize the end-to-end persistent execution and verify speedup.

- [ ] Task: Finalize Hot Loop in `executor.py`
    - [ ] Ensure the main render loop correctly cycles through recipes without teardown.
- [ ] Task: Validate Correctness & Benchmarking
    - [ ] Compare "Hot" results against "Cold" baseline for pixel consistency.
    - [ ] Produce final performance report (Cold vs. Hot speedup).
- [ ] Task: Run Full Test Suite
    - [ ] Ensure no regressions in complex scenarios (Industrial, AprilGrid).
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final Integration' (Protocol in workflow.md)
