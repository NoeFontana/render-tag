# Specification: Voxel51 Visualization & Debugging Tool

## Overview
Implement a robust, decoupled visualization and debugging tool using Voxel51 (FiftyOne) for the `render-tag` ecosystem. The tool enables high-fidelity inspection of synthetic datasets, joining standard COCO annotations with custom "rich truth" metadata for deep programmatic auditing and visual verification of geometric contracts.

## Functional Requirements
- **CLI Integration:** Implement `render-tag viz fiftyone --dataset <path>` command to launch the visualization suite.
- **Data Ingestion (ETL):** 
    - Standard COCO importer for images, bounding boxes, and polygons.
    - Custom metadata hydration from `rich_truth.json` using a composite key (`image_id` + `tag_id`).
- **Geometric Mapping:**
    - **Bounding Box Layer:** Coarse check for canvas resolution and clipping.
    - **Polygon Layer:** Maps COCO `segmentation` to FiftyOne `Polyline` for affine transform verification.
    - **Keypoint Layer:** Maps ordered corners to labeled `Keypoints` ("0", "1", "2", "3") to expose winding order and orientation.
- **Metadata Integration:** Custom fields for `distance`, `angle_of_incidence`, `ppm`, `position`, and `rotation_quaternion` on every detection.
- **Automated Auditor ("Watchdog"):** Programmatic tagging of anomalies:
    - `ERR_OOB`: Out-of-bounds or invalid coordinates (e.g., `-1e6` bug).
    - `ERR_OVERLAP`: Overlap between tags on a board (IoU-based).
    - `ERR_SCALE_DRIFT`: Contradictions between calculated `ppm` and bounding box pixel area.
- **Headless Mode:** Support for remote deployment on compute clusters with web port exposure.

## Non-Functional Requirements
- **Decoupling:** Modular architecture separated from core rendering logic.
- **Performance:** Optimized indexing for rapid metadata merging across large datasets.
- **UI/UX:** Sidebar filters for all rich truth metrics and index-based color-coding for keypoints.

## Acceptance Criteria
- [ ] `render-tag viz fiftyone` successfully launches the FiftyOne App on a single dataset.
- [ ] All "rich truth" metrics (e.g., PPM, angle) are available as sliders in the FiftyOne sidebar.
- [ ] Visual verification of winding order is possible via color-coded, labeled keypoints.
- [ ] Anomalous samples are automatically tagged by the watchdog script.
- [ ] Tool runs successfully in headless mode for remote access.

## Out of Scope
- Cross-experiment benchmarking or multi-dataset aggregation.
- Real-time visualization during generation.
