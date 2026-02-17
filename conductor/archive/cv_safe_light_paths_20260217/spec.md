# Specification: "CV-Safe" Light Paths Optimization

## Overview
This track optimizes the Blender rendering engine's light path calculations specifically for Computer Vision (CV) tasks. Standard 3D rendering often uses high bounce counts and caustics for photorealism, which are computationally expensive and offer diminishing returns for training CV models. This optimization "kills" unnecessary calculations (caustics, transmission) while preserving critical features like specular highlights (glare) that are essential for robust tag detection.

## Functional Requirements
- **Configurable Light Bounces:** Extend `RendererConfig` to support granular control over:
    - `total_bounces` (default: 4)
    - `diffuse_bounces` (default: 2)
    - `glossy_bounces` (default: 4)
    - `transmission_bounces` (default: 0)
    - `transparent_bounces` (default: 4)
- **Caustics Control:** Add a toggle `enable_caustics` (default: False) to disable reflective and refractive caustics.
- **Backend Integration:** Update `src/render_tag/backend/engine.py` to apply these light path settings to the BlenderProc renderer.
- **Hybrid Configuration:** Users can override individual bounce counts in their experiment YAMLs while benefiting from CV-optimized defaults.

## Non-Functional Requirements
- **Performance:** Reduced render times by eliminating complex light path calculations (caustics, high diffuse/transmission bounces).
- **Fidelity for CV:** Preserves glossy reflections/glare on tags, ensuring detection models are tested against realistic lighting artifacts.

## Acceptance Criteria
- [ ] `RendererConfig` schema updated with new light path parameters and CV-optimized defaults.
- [ ] Rendering engine correctly applies bounce counts and caustics settings to BlenderProc.
- [ ] Verification that disabling caustics and reducing transmission bounces yields performance gains without degrading tag edge quality.
- [ ] Unit tests verify that overriding individual parameters in YAML is respected.

## Out of Scope
- Global Illumination (GI) algorithm changes (e.g., switching from Path Tracing to something else).
- Per-material light path overrides.
