# Coordinate Systems

This document defines the canonical coordinate systems used within the `render-tag` pipeline.

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

## 3. Keypoint Convention
- **Ordering:** Row-major, zero-indexed.
- **Topology:** Continuous numbering starting from the Top-Left corner (Row 0, Col 0).
