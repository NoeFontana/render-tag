# Implementation Plan: Voxel51 Visualization & Debugging Tool

## Phase 1: Environment & CLI Scaffolding [checkpoint: 2c25d13]
Establish the foundational infrastructure for FiftyOne integration.
- [x] Task: **Add FiftyOne dependencies** to `pyproject.toml` and synchronize environment (`uv sync`). (5cda79c)
- [x] Task: **Create CLI scaffold** for `render-tag viz fiftyone --dataset <path>`. (1d28c55)
- [x] Task: **Define FiftyOne Schema** for custom metadata fields (`distance`, `ppm`, `angle`, `position`, `rotation`). (1fefd09)
- [x] Task: **Conductor - User Manual Verification 'Phase 1: Environment & CLI Scaffolding' (Protocol in workflow.md)** (2c25d13)

## Phase 2: ETL Layer (Data Ingestion & Schema Definition) [checkpoint: 5301813]
Develop the core logic for loading and indexing dataset artifacts.
- [x] Task: **Write Tests: COCO and Rich Truth Loader** (Success/Failure cases). (27ae935)
- [x] Task: **Implement COCO Ingestion** using FiftyOne standard importer. (27ae935)
- [x] Task: **Implement Rich Truth Indexing** for rapid lookup by `image_id` + `tag_id`. (27ae935)
- [x] Task: **Verify ETL Pipeline** on a sample dataset (`output/test_results`). (c4fa1ec)
- [x] Task: **Conductor - User Manual Verification 'Phase 2: ETL Layer' (Protocol in workflow.md)** (5301813)

## Phase 3: Geometric Representation & Metadata Mapping [checkpoint: 35b0348]
Translate raw annotations into visual layers for deep debugging.
- [x] Task: **Write Tests: Keypoint and Polygon Mapping** (Winding order validation). (d3b0928)
- [x] Task: **Implement Polygon Mapping** from COCO `segmentation` to FiftyOne `Polyline`. (d3b0928)
- [x] Task: **Implement Labeled Keypoint Mapping** from `rich_truth.json` with indexed labels ("0", "1", "2", "3"). (d3b0928)
- [x] Task: **Implement Metadata Hydration** to populate FiftyOne `Detection` objects with physics/rendering metrics. (d3b0928)
- [x] Task: **Conductor - User Manual Verification 'Phase 3: Geometric Representation' (Protocol in workflow.md)** (35b0348)

## Phase 4: Automated Auditing & Tagging ("Watchdog") [checkpoint: 2ade5f5]
Leverage the FiftyOne API to programmatically flag data quality issues.
- [x] Task: **Write Tests: Auditing Logic** (OOB, Overlap, Scale drift). (5e630b2)
- [x] Task: **Implement Out-of-Bounds Detector** to flag `ERR_OOB` anomalies. (5e630b2)
- [x] Task: **Implement IoU-based Overlap Detector** for tags to flag `ERR_OVERLAP`. (5e630b2)
- [x] Task: **Implement Scale-Drift Validator** (PPM vs. Bbox area) to flag `ERR_SCALE_DRIFT`. (5e630b2)
- [x] Task: **Conductor - User Manual Verification 'Phase 4: Automated Auditing' (Protocol in workflow.md)** (2ade5f5)

## Phase 5: Dashboard Configuration & Final Verification [checkpoint: e4cc425]
Polish the UI experience and ensure cluster-readiness.
- [x] Task: **Configure App UI** (Sidebar sliders, custom color-coding for keypoints). (29fbd34)
- [x] Task: **Implement Headless Support** for remote server deployment. (29fbd34)
- [x] Task: **Final Integration Test** on a full-scale generated dataset. (29fbd34)
- [x] Task: **Conductor - User Manual Verification 'Phase 5: Dashboard Configuration' (Protocol in workflow.md)** (e4cc425)
