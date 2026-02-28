# Specification: 3D-Anchored Orientation Contract

## Overview
This track eliminates 'orientation loss' in synthetic tag data by shifting the source of truth for corner ordering from 2D image-space heuristics to a strict 3D local-space asset contract. By binding 'Logical Corners' to the 3D mesh and using a pure mathematical passthrough during projection, we ensure that the orientation (roll/pitch/yaw) is perfectly preserved in the ground-truth annotations.

## Functional Requirements
- **FR1: Logical Corner Contract:** Index 0 must always represent the **Logical Top-Left** of the tag (relative to its local X/Y axes). Indices 1, 2, and 3 must follow a **Clockwise** winding in local 3D space (TR, BR, BL).
- **FR2: Standardized 3D Metadata:** Replace the temporary `corner_coords` property with a standardized `keypoints_3d` property on all tag objects in the Blender backend.
- **FR3: Correct Asset Generation:** Update `create_tag_plane` in `assets.py` to explicitly calculate and assign these 4 local coordinates to the `keypoints_3d` property.
- **FR4: Pure Projection Engine:** 
    - Remove the `sort_corners` heuristic from `projection.py`.
    - Update the projection engine to retrieve `keypoints_3d`, project them to 2D, and preserve their original array index in the final `DetectionRecord`.
- **FR5: Geometric Invariance Suite:** Implement a set of automated tests that verify:
    - **Upright Case:** Logical 0 is at visual Top-Left when tag is facing camera.
    - **Inverted Case:** Logical 0 is at visual Bottom-Right when tag is rolled 180 degrees.
    - **Skew Case:** Clockwise winding is maintained even under extreme perspective distortion.

## Non-Functional Requirements
- **NFR1: Mathematical Purity:** The projection layer must perform NO conditional sorting based on visual coordinates.
- **NFR2: Performance:** Accessing `keypoints_3d` custom properties should be as efficient as the previous `corner_coords` implementation.

## Acceptance Criteria
- `sort_corners` is removed from the project or marked as deprecated (to be removed).
- All generated `tags.csv` or `coco_labels.json` entries reflect the logical payload order, regardless of tag roll.
- CI tests for Upright, Inverted, and Skewed cases pass consistently.
- Documentation in `ARCHITECTURE.md` is updated to reflect the new 3D-first orientation contract.

## Out of Scope
- Modifying the visual appearance of the tags themselves.
- Changing the existing COCO keypoint format structure (only the index mapping changes).
