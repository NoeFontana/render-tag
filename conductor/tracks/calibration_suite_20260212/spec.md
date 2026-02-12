# Specification: Calibration & Ground Truth Suite (Phase 1)

## Overview
This track implements Phase 1 of the "Locus Bench" suite, focusing on establishing a sub-pixel accurate baseline for corner refinement. It involves creating a dedicated "Calibration" campaign in `render-tag` to generate mathematically perfect synthetic data for both standard checkerboards and AprilGrids, enabling direct accuracy comparison with OpenCV.

## Functional Requirements
- **Automated Directory Hierarchy**: The generation process must automatically enforce the `data/locus_bench_v1/01_calibration/` structure, separating static checkerboards from dynamic AprilGrids.
- **Calibration Experiments**: 
    - `01_checkerboard.yaml`: Static, uniform lighting, pinhole camera, generating ground truth COCO corners.
    - `02_aprilgrid.yaml`: Slow rotation (dynamic), standard 36h11 family, generating ground truth COCO corners.
- **COCO Corner Ground Truth**: Annotations must include high-precision `corners_2d` formatted as COCO keypoints `[x, y, visibility]`.
- **Self-Describing Metadata**: Every sub-dataset must include a `dataset_info.json` containing:
    - `intent`: (e.g., "calibration_cv" or "calibration_tag")
    - `geometry`: Square size (mm) and grid dimensions.
    - `provenance`: Git commit, `render-tag` version, and Blender version.
    - `integrity`: SHA-256 fingerprint of the data files.

## Non-Functional Requirements
- **Determinism**: The experiments must lock all RNG seeds to ensure pixel-perfect reproducibility.
- **Visualization**: Support `render-tag viz` to overlay ground truth corners on generated images for immediate visual verification.

## Acceptance Criteria
- `render-tag experiment --config configs/experiments/locus_bench_p1.yaml` produces the correct directory structure.
- `dataset_info.json` is present in every output folder with valid checksums and metadata.
- Generated annotations contain `corners_2d` in COCO format that align perfectly with image features when visualized.
- The repository size remains unaffected (ensuring large outputs are ignored by Git).

## Out of Scope
- Camera lens distortion (reserved for future phases).
- Integration with the `locus-tag` library itself (this track only provides the data).
