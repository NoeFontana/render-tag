# Specification - Persistent Data & Scene Recycling ("Hot Loop")

## Overview
Currently, the `executor.py` backend relies on a fresh initialization for every render or shard, leading to significant overhead in Blender start-up, asset loading, and plugin registration. This track implements a "Hot Loop" optimization where Blender remains active, recycling scene objects, materials, and world settings between renders. This ensures assets remain warm in VRAM, dramatically reducing Mean Time Per Frame (MTPF).

## Functional Requirements
- **Recycling Layer:**
    - Refactor `executor.py` to maintain a persistent world state.
    - Implement an **Object Pool** for tag planes to avoid creation/deletion overhead.
    - Implement **Lazy Loading** for world HDRIs: Only swap the `World` node tree if the requested HDRI path differs from the current active one.
- **Memory Management:**
    - Use a fixed set of material slots for tags, updating image texture references in-place.
    - Implement **Hybrid Garbage Collection**: Periodically purge orphaned data blocks (e.g., every 50 scenes) to prevent VRAM saturation.
- **Data Ingestion:**
    - Update the backend to accept a list of scene recipes and iterate through them without exiting the Python execution context.

## Non-Functional Requirements
- **Performance:** Achieve a significant speedup (target >30%) for batch generation tasks (100+ scenes).
- **Stability:** Maintain consistent VRAM usage over 1,000+ continuous renders.
- **Transparency:** The "Hot Loop" should be an internal implementation detail; the CLI interface remain identical.

## Acceptance Criteria
- [ ] `executor.py` processes multiple recipes within a single Blender session.
- [ ] Visual artifacts (e.g., "bleeding" of assets from previous scenes) are non-existent.
- [ ] Benchmarking confirms a reduction in average per-scene overhead (time spent NOT rendering).
- [ ] VRAM usage stabilizes after the initial asset loading phase.

## Out of Scope
- Implementation of a persistent Blender daemon (Socket/REST API). This track focuses on loop-level persistence within a single process run.
