# Specification: High-Fidelity Calibration Targets (ChArUco & AprilGrid)

## Overview
This track implements mathematically perfect calibration targets using **Texture Synthesis**. By generating a single high-resolution texture and applying it to a rigid 3D plane, we eliminate the geometric drift and Z-fighting inherent in multi-object layouts. The system will support the industry-standard Kalibr AprilGrid and OpenCV ChArUco formats.

## Functional Requirements

### 1. Parametric Board Schema (`BoardConfig`)
- Implement a unified configuration that handles the distinct logic of both boards:
    - **AprilGrid**: Defined by `marker_size` (black tag width) and `spacing_ratio` (gap between tags). Pitch is derived.
    - **ChArUco**: Defined by `square_size` (checkerboard cell) and `marker_size` (inner tag width).
- Support standard dictionaries (e.g., `tag36h11` for AprilGrid, `DICT_4X4_50` for ChArUco).

### 2. Bit-Perfect Texture Synthesizer (`TextureFactory`)
- Use **OpenCV** to draw textures at high resolution (target: 10px/mm or higher).
- **Anti-Aliasing Control**: Render edges with zero interpolation (hard pixel boundaries) to ensure the sub-pixel corner refinement algorithms in estimator tools receive sharp gradients.
- **Cache Management**: Textures must be content-addressed (hashed) to avoid redundant generation.

### 3. Rigid Scene Integration
- **Single Plane Architecture**: Backend spawns one plane object scaled to total board dimensions.
- **UV Precision**: Force 1:1 UV mapping with no border bleeding.
- **Pose Sampling**: Implement a `BOARD` layout mode that treats the board as a single rigid body originating at `(0,0,0)`.

### 4. Calibration-Grade Data Export
- **Board Sidecar**: Export `board_config.json` containing the ground-truth geometry (rows, cols, square/marker sizes) required by estimators.
- **Dual-Ground Truth**:
    - `projected_2d`: Mathematically perfect pinhole projection.
    - `distorted_2d`: Post-lens distortion coordinates.
- **Keypoint Differentiation**: 
    - AprilGrid: Export the 4 corners of the black border for every tag.
    - ChArUco: Export the **Saddle Points** (checkerboard intersections).

## Non-Functional Requirements
- **Geometric Rigidity**: Keypoint coordinates in the export must match the visual texture with sub-millimeter accuracy.
- **Sub-pixel Determinism**: The projection math must be scalar-first and environment-independent.

## Acceptance Criteria
- [ ] `BoardConfig` schema validated and integrated into `GenConfig`.
- [ ] `TextureFactory` produces accurate PNGs for both prioritized board types.
- [ ] Backend renders boards as single planes with perfect texture alignment.
- [ ] `board_config.json` is exported with the dataset.
- [ ] `rich_truth.json` includes accurate 3D/2D keypoints (Saddle points for ChArUco).
- [ ] **Verification Pass**: A flat render test at 1.0m shows corner spacing matching theoretical pixel distances within 0.1px.

## Out of Scope
- Support for 3D/Non-planar targets.
- Standard (markerless) checkerboards (prioritized for Phase 2).
