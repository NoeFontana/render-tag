---
license: mit
task_categories:
  - synthetic-data-generation
  - computer-vision
tags:
  - synthetic
  - apriltag
  - adversarial
  - domain-randomization
language:
  - en
pretty_name: Render-Tag Assets
size_categories:
  - n<1K
---

# Render-Tag Assets

This dataset contains asset files used by the `render-tag` synthetic data generation pipeline.

## Structure

### Textures (`textures/`)
Background and object textures used for domain randomization.

- **Backgrounds**:
  - `background/adversarial/`: High-frequency, repetitive, or complex patterns designed to challenge tag detectors (e.g., QR code grids, text, tiles).
  - `background/natural/`: Common environmental textures (e.g., carpet).

### Tags (`tags/`)
Reference images for Fiducial Marker families.

- `tag36h11/`: Standard AprilTag 36h11 family.

## Usage

These assets are designed to be used with the [render-tag](https://github.com/example/render-tag) library.
