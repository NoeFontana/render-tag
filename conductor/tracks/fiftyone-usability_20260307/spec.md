# Specification: FiftyOne Integration Usability Improvements

## Overview
As a Principal Engineer, improve the Voxel51 (FiftyOne) integration to enhance usability for debugging synthetic datasets. This track focuses on smarter session management, actionable saved views, and high-fidelity visual overlays that align with computer vision standards (OpenCV/ArUco).

## Functional Requirements
- **Smart Session Management:** Implement logic to reuse existing FiftyOne app instances if they are already running on the target port, preventing "Address already in use" errors and speeding up subsequent launches.
- **Actionable Saved Views:** Pre-configure "Saved Views" in the FiftyOne sidebar, specifically an **Error View** that instantly filters the dataset for samples tagged with `ERR_OOB`, `ERR_OVERLAP`, or `ERR_SCALE_DRIFT`.
- **Standard CV Overlays:** Implement visual overlays for tags that mimic standard OpenCV ArUco/AprilTag debugging styles:
    - **Coordinate Axes:** Draw X (Red), Y (Green), and Z (Blue) axes at the center of each detected tag.
    - **ID Labels:** Display the tag ID clearly at the center or corner of the bounding box.
- **Improved ETL Feedback:** Enhance the CLI progress reporting during the COCO ingestion and rich-truth hydration phases.

## Non-Functional Requirements
- **Consistency:** Ensure overlays use the same coordinate system and color conventions as OpenCV.
- **Performance:** Maintain low latency when rendering axes overlays across large datasets.
- **Simplicity:** Keep the dataset ephemeral; do not introduce persistent database overhead.

## Acceptance Criteria
- [ ] Running `render-tag viz fiftyone` when a session is already active reuses the existing window/tab.
- [ ] A sidebar preset exists to show only samples with detected anomalies.
- [ ] Tags in the FiftyOne UI display 3D axes and ID labels.
- [ ] Automated tests verify the session reuse and overlay generation logic.

## Out of Scope
- Support for multiple concurrent datasets in one FiftyOne instance.
- Persistent local storage of FiftyOne datasets between machine reboots.
