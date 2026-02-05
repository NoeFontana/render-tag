# Specification: Hot Loop Optimization (Persistent Backend)

## Overview
Transition the rendering pipeline from a "cold" per-image startup model to a high-throughput, persistent backend architecture. This track implements a "Hot Loop" where Blender processes remain active across multiple renders, utilizing ZeroMQ for communication and object pooling to maximize VRAM efficiency and throughput.

## Functional Requirements

### 1. Persistent Blender Backend
- Implement a long-lived Blender process that stays resident in memory between individual scene renders.
- Minimize initialization overhead by avoiding repeated startup of the Blender executable and BlenderProc modules.

### 2. ZeroMQ Communication Layer
- Utilize ZeroMQ (ZMQ) for a structured, high-performance command-and-control channel between the Host application and Backend workers.
- Define a JSON-based protocol for:
    - `INIT`: Pre-loading heavy assets (Warm-up phase).
    - `RENDER`: Executing a specific scene recipe.
    - `RESET`: Fast partial reset of volatile scene state (camera, tag pose).
    - `STATUS`: Heartbeats and telemetry (VRAM usage, state hashes).

### 3. Managed Worker Pool
- Implement a host-side orchestrator to manage a pool of persistent workers.
- Support active health monitoring and automatic worker restarts in case of crashes or resource leaks.

### 4. Scene Recycling & Object Pooling
- Implement logic to keep heavy assets (HDRIs, industrial occluders, tag textures) resident in VRAM.
- Provide "Partial Reset" capabilities to swap volatile components without reloading the entire environment.

## Non-Functional Requirements
- **Performance**: Aim for a throughput increase of ~10x (from ~10 to ~100+ images/min for standard scenes).
- **Reliability**: Implement "VRAM Guardrails" to monitor memory pressure and prevent OOM errors.
- **Reproducibility**: Use "State Hashing" to ensure the backend state matches the host's intended recipe.

## Acceptance Criteria
- [ ] A persistent Blender worker can process 100 consecutive recipes without restarting.
- [ ] ZeroMQ latency for command transmission is < 5ms.
- [ ] VRAM usage remains stable (within 10% variance) after the initial warm-up phase.
- [ ] Successful "State Hash" verification for every render in a batch.

## Out of Scope
- Multi-node/Multi-GPU distribution (to be handled by the existing sharding layer).
- Real-time interactive viewport (focus remains on offline dataset generation).
