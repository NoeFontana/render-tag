# Specification: Pose Estimation Baseline (Phase 2)

## Overview
This track transforms `render-tag` into a declarative "Data Platform" for benchmarking. It defines a strict API for generating pose estimation baselines using a master Experiment Manifest. This ensures that the `locus-tag` benchmark suite receives mathematically perfect data for measuring RMSE jitter and grazing angle robustness using unit quaternions for orientation.

## Functional Requirements
- **Declarative API**: Implement `configs/experiments/locus_pose_baseline.yaml` as the single source of truth for the Phase 2 suite.
- **Clean Room Presets**: 
    - `distance.yaml`: Static frames, 1m to 30m sweep, ambient lighting, pinhole model.
    - `angle.yaml`: 0 to 85-degree rotation sweep, three-point lighting for surface clarity.
    - All presets must be fully overridable via experiment overrides.
- **Quaternion Pose GT**: Per-frame annotations must include the relative camera-to-tag transformation using the following schema:
    - `position`: `[x, y, z]` (Translation vector in meters).
    - `rotation_quaternion`: `[w, x, y, z]` (Unit quaternion, scalar-first).
- **Contractual Metadata (dataset_info.json)**: Every dataset must include a validated manifest containing:
    - `camera_intrinsics`: focal length, principal point, resolution.
    - `tag_specification`: `tag_family` and `tag_size_mm` (integer).
    - `pose_convention`: Explicitly declare `"wxyz"` to ensure cross-ecosystem compatibility.
    - `sweep_definition`: `variable_name` and `range` for automated analysis.

## Non-Functional Requirements
- **Mathematical Purity**: Zero lens distortion and zero motion blur (`velocity_max: 0.0`) by default.
- **Geodesic Stability**: Use Quaternions to allow for robust shortest-path error calculation on the SO(3) manifold.
- **Schema Enforcement**: Use Pydantic models to validate the `dataset_info.json` contract.

## Acceptance Criteria
- Running `uv run render-tag experiment run configs/experiments/locus_pose_baseline.yaml` generates `02_pose_distance_sweep` and `02_pose_angle_sweep`.
- `dataset_info.json` in each output directory passes Pydantic validation and contains `convention: "wxyz"`.
- JSON annotations contain the `position` and `rotation_quaternion` fields for every tag.
- `tag_size_mm` is an integer value (e.g., 160).

## Out of Scope
- Dynamic motion blur or rolling shutter (reserved for Phase 3).
- Complex environmental textures (using flat colors only).
