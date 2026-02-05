# Specification - Simulation of Rolling Shutter Effect

## Overview
This track implements rolling shutter simulation to bridge the sim-to-real gap for robotics applications. Unlike global shutter cameras, CMOS sensors scan row-by-row, causing geometric warping (e.g., parallelograms instead of squares) when the camera or objects are moving at high velocity. This warping is critical for realistic benchmarking of tag detection and pose estimation.

## Functional Requirements
- **Configuration Schema:**
    - Add `rolling_shutter_duration_ms: float` to the `CameraConfig` within a new `sensor_dynamics` grouping (alongside existing motion blur settings).
    - Validation: Ensure duration is non-negative and physically plausible relative to frame rates.
- **Backend Implementation (Blender):**
    - **Cycles Support:** Map the configuration value to `bpy.context.scene.render.rolling_shutter_duration`.
    - **Eevee/Workbench Support:** Provide a warning if rolling shutter is enabled but the engine doesn't support it natively.
    - **Scan Direction:** Hardcode or default to Top-to-Bottom (Standard CMOS behavior).
- **Ground Truth Consistency:**
    - Ground-truth corner annotations and bounding boxes will represent the **Ideal Pose** at the center of the exposure time, rather than the warped pixel positions. This maintains compatibility with standard detector training pipelines.

## Non-Functional Requirements
- **Performance:** Native Cycles rolling shutter simulation should have minimal impact on render time compared to standard motion blur.
- **Scientific Integrity:** The implementation must accurately reflect the geometric shearing effect caused by row-wise scanning.

## Acceptance Criteria
- [ ] `render-tag generate` accepts a configuration with `rolling_shutter_duration_ms`.
- [ ] Renders of moving objects (or moving cameras) show visible geometric shearing in Cycles.
- [ ] A warning is issued when using Eevee with rolling shutter enabled.
- [ ] Ground truth annotations remain centered on the object's "true" pose at mid-exposure.
