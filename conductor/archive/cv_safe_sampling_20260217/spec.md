# Specification: "CV-Safe" Sampling Strategy (Adaptive + OIDN)

## Overview
This track introduces a "CV-Safe" rendering strategy to optimize throughput without compromising the accuracy of Computer Vision (CV) tasks like AprilTag detection and pose estimation. By utilizing adaptive sampling with a noise threshold and Intel OpenImageDenoise (OIDN) guided by Albedo and Normal passes, we can significantly reduce render times while preserving the sharp edges required for precise corner refinement.

## Functional Requirements
- **Adaptive Sampling:** Implement support for `noise_threshold` and `max_samples` in the rendering pipeline.
- **Guided Denoising:** Integrate Intel OIDN with Albedo and Normal pass guidance to ensure high-frequency edges (like tag corners) are not blurred.
- **Configurable Parameters:** Expose the following parameters in the `RendererConfig` (and thus experiment YAMLs):
    - `noise_threshold` (float): Target noise level (default: 0.05).
    - `max_samples` (int): Maximum samples per pixel (default: 128).
    - `enable_denoising` (bool): Toggle for OIDN (default: True).
    - `denoiser_type` (str): Choice of denoiser (default: "INTEL").
- **Backend Integration:** Update `src/render_tag/backend/engine.py` to apply these settings to the BlenderProc renderer.

## Non-Functional Requirements
- **Edge Preservation:** The denoising process MUST NOT degrade the sub-pixel accuracy of AprilTag corner detection.
- **Performance:** Rendering speed should significantly improve for scenes with simple backgrounds compared to fixed-sample rendering.

## Acceptance Criteria
- [ ] Users can specify `noise_threshold`, `max_samples`, and `denoising` settings in the experiment config.
- [ ] The rendering engine correctly applies these settings to BlenderProc.
- [ ] Denoising successfully uses Albedo and Normal passes for guidance.
- [ ] A "sanity check" test verifies that "CV-Safe" renders maintain corner sharpness comparable to high-sample renders (e.g., 512+ samples).
- [ ] Existing benchmarks are updated to use these efficient defaults.
- [ ] Documentation explains the new parameters and their impact on CV performance.

## Out of Scope
- Implementation of non-OIDN denoisers (unless trivial to expose).
- Real-time rendering optimizations outside of the offline generation pipeline.
