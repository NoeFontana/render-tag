# Coordinate Systems & Data Standards

This document defines the canonical coordinate systems and data export standards used within the `render-tag` pipeline.

## 1. Canonical Board Frame (Local Space)

When defining the geometry of a calibration board (ChArUco, AprilGrid, Checkerboard, etc.), we follow a **Computer Vision (CV) Standard** mapping. This ensures seamless integration with libraries like OpenCV and Kalibr.

### Origin and Axes
- **Origin (0,0,0):** The physical **Top-Left** corner of the board's active area.
- **+X Axis:** Left-to-Right (traversing Columns).
- **-Y Axis (Blender Local):** Top-to-Bottom (traversing Rows).

### Why the -Y Axis?
In the Blender Cartesian coordinate system, `+Y` points "Up". However, in standard image sensors and computer vision libraries, `+Y` points "Down". 
To bridge this gap without introducing mirroring or 180-degree rotation errors:
1. Row 0 (the top row) is located at the board's physical top.
2. Subsequent rows ($R > 0$) move in the **negative Y direction** in Blender's local space.

### Physical Mapping
For a board of size $(W, H)$:
- **Top-Left Corner:** $(0, 0, 0)$ relative to the board's top-left origin.
- **In Blender Global Space (if board is centered):**
  - Row 0, Col 0: $(-W/2, +H/2, 0)$
  - Row R, Col C: $(-W/2 + C \cdot square\_size, +H/2 - R \cdot square\_size, 0)$

## 2. Global Scene Space
- **Z-Up:** Blender's default world coordinate system.
- **Camera Orientation:** Standard OpenCV camera model (Z forward, X right, Y down).

## 3. Data Export Standards (For Downstream Users)

The annotations in `coco_labels.json`, `rich_truth.json`, and `*_meta.json` follow strict geometric contracts to ensure compatibility with computer vision benchmarks.

### Relative Pose (Object-to-Camera)
The pose represents the transformation from the **Object Local Space** (defined above) to the **Camera OpenCV Space**.

*   **Coordinate System:** OpenCV Convention (+X Right, +Y Down, +Z Forward).
*   **Position (`position`):** A 3-element list `[x, y, z]` in meters.
*   **Active Size (`tag_size_mm`):** The physical edge length of the black border in millimeters. Use this value for PnP and scale-dependent pose estimation.
*   **Intrinsics (`k_matrix`, `resolution`):** Injected directly into each detection record in `rich_truth.json` and `coco_labels.json`.
*   **Rotation (`rotation_quaternion`):** 
    *   **Format:** **`[x, y, z, w]` (Scalar-Last)** in all exported JSON/CSV files.
    *   *Note: Internally, the pipeline uses `[w, x, y, z]`, but performs a flip at the IO boundary for SciPy/Ceres compatibility.*

### Camera Intrinsics
Found in the `recipe_snapshot` within `*_meta.json` sidecar files, and also duplicated in each detection record for convenience.

*   **Intrinsic Matrix (K):** 3x3 matrix in the following format:
    ```python
    [[fx,  0, cx],
     [ 0, fy, cy],
     [ 0,  0,  1]]
    ```
*   **Principal Point (`cx`, `cy`):** Defaults to the exact image center (`width / 2`, `height / 2`).
*   **Distortion:** Currently exported as zero (perfect pinhole) for the 2026 baseline, following the `(k1, k2, p1, p2, k3)` OpenCV order.

### Physical Size vs. Annotated Corners
There is a critical distinction between the physical plane size and the ground truth annotations:

*   **`size_meters`**: Defines the **outer edge** of the entire tag asset, including the white quiet zone (margin).
*   **Annotated Corners**: Represent the **outer edge of the black border** only. 

The distance from the physical edge to the annotated corner is determined by the `margin_bits` parameter. For a tag with $N$ bits and a margin of $M$ bits, the annotated corners are located at a scale of $N / (N + 2M)$ relative to the physical center.

### Keypoint Convention
- **Ordering:** Row-major, zero-indexed.
- **Topology:** Continuous numbering starting from the Top-Left corner (Row 0, Col 0).
- **Winding:** All projected 2D corners follow a **Strictly Clockwise (CW)** winding order in the image plane (Y-down).
