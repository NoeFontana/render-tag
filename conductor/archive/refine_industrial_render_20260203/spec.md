# Specification - Refine Industrial Rendering & Sensor Simulation

## Overview
This track focuses on enhancing the photorealism and sensor accuracy of the `render-tag` pipeline, specifically targeting industrial and outdoor scenarios. The goal is to reduce the sim-to-real gap for tag detection models by introducing more complex environmental factors and realistic camera artifacts.

## Functional Requirements
- **Advanced Sensor Noise:** Implement parametric sensor noise models (e.g., Gaussian, Poisson, salt-and-pepper) beyond simple global intensity adjustments.
- **Industrial Lighting Presets:** Create or refine HDRi-based lighting setups specifically for industrial environments (factories, warehouses).
- **Motion Blur Refinement:** Improve the procedural motion blur calculation based on realistic camera exposure times and tag-to-camera relative velocity.
- **Surface Imperfections:** Introduce procedural textures for tag surfaces to simulate scratches, dust, and non-uniform specularity.

## Non-Functional Requirements
- **Validation Consistency:** Ensure all new parameters are strictly validated via the existing Pydantic schema.
- **Shadow Render Support:** All new rendering features must have a representative placeholder in the "Shadow Render" loop for fast verification.

## Acceptance Criteria
- [ ] New sensor simulation parameters are configurable via YAML.
- [ ] Rendered images show visible improvements in noise and lighting complexity compared to the current baseline.
- [ ] The `validate-recipe` command passes for scenes using the new features.
- [ ] Integration tests verify that annotations remain accurate despite increased image complexity.
