# Coordinate Systems & Data Standards

This document defines the canonical coordinate systems, geometric contracts, and data export standards used within the `render-tag` pipeline. It serves as the single source of truth for downstream users and applications.

## 1. Geometric Contracts

### 1.1 The Orientation Contract (3D & 2D)
To ensure zero-ambiguity in pose estimation and keypoint association, every asset in `render-tag` adheres to a strict index-based orientation contract. The coordinate system is tied to the order in which corners are detected:

- **Corner 0:** Top-left of the marker (when oriented upright).
- **Corner 1:** Top-right.
- **Corner 2:** Bottom-right.
- **Corner 3:** Bottom-left.

This strictly clockwise (CW) winding order is preserved through the entire projection pipeline and is reflected in the `corners` and `keypoints` fields of all exported JSON/CSV files.

### 1.2 Canonical Board Frame (Local Space)
When defining the geometry of a calibration board (ChArUco, AprilGrid), we follow a mapping designed for Computer Vision (CV) library compatibility.

#### Origin and Axes
- **Origin (0,0,0):** Anchored at the **mathematical center** of the active black border (for single markers) or the geometric center of the board (for ChArUco and AprilGrid boards). This matches the native behavior of AprilTag, ArUco, and locus-tag detectors.
- **+X Axis:** Points Right.
- **+Y Axis:** Points Down.
- **+Z Axis:** Points **into the board plane** (away from the viewer), following the standard OpenCV camera convention.

#### Visual Mapping (Local Space)

```text
             Local Coordinate System (Local XY Plane)
             Origin (0,0,0) at Geometric Center

       (-w/2, -h/2)                          (+w/2, -h/2)
          [Corner 0] ________________________ [Corner 1]
               |    |                        |    |
               |    |        -Y (Up)         |    |
               |    |           ^            |    |
               |    |           |            |    |
               |    |   -X <--- O ---> +X    |    |
               |    |   (Left)  |   (Right)  |    |
               |    |           |            |    |
               |    |        +Y (Down)       |    |
               |    |________________________|    |
          [Corner 3]                          [Corner 2]
       (-w/2, +h/2)                          (+w/2, +h/2)

    +Z Axis: Points INTO the board (away from camera).
    Corners: Outer edge of the BLACK BORDER.
```

The board's mathematical layout treats **+Y as pointing downwards** and **+Z as pointing inwards**. With the origin at center:
1. The Top-Left corner is at local coordinates \\((-w/2, -h/2, 0)\\).
2. The Bottom-Right corner is at local coordinates \\((+w/2, +h/2, 0)\\).
3. The surface normal facing the camera represents the **-Z** direction.

### 1.3 Calibration Board Layouts
For multi-marker arrays like **ChArUco** or **AprilGrid**, the origin remains at the geometric center of the entire board. Markers are indexed in **row-major order** starting from the top-left.

#### Board Indexing & Keypoints

```text
             Board Layout (Origin at Geometric Center)
             Example: 2x3 Grid (Rows x Cols)

       Row 0, Col 0      Row 0, Col 1      Row 0, Col 2
      [ Marker 0 ]      [ Marker 1 ]      [ Marker 2 ]
          (0,0)             (0,1)             (0,2)
            |                 |                 |
       Row 1, Col 0      Row 1, Col 1      Row 1, Col 2
      [ Marker 3 ]      [ Marker 4 ]      [ Marker 5 ]
          (1,0)             (1,1)             (1,2)

    Keypoint Indexing:
    - Within each Marker: 0, 1, 2, 3 (CW winding)
    - Board Total: Continuous row-major (0 to N-1)
```

**ChArUco Saddle Points:**
For ChArUco boards, calibration "saddle points" (checkerboard corners) are interleaved between markers. These are also exported in row-major order.
-   **Origin (0,0):** Top-left-most internal corner.
-   **Total Corners:** \\((R-1) \times (C-1)\\) where \\(R, C\\) are the number of grid squares.

## 2. Global Scene Space
- **World Frame:** Z-Up (Blender default).
- **Camera Orientation:** Standard OpenCV camera model (**+Z forward, +X right, +Y down**).

## 3. Data Export Standards (For Downstream Users)

The annotations in `coco_labels.json`, `rich_truth.json`, and `provenance.json` follow strict geometric contracts.

### 3.1 Relative Pose (Object-to-Camera)
The pose represents the transformation from the **Tag Center** (defined above) to the **Camera OpenCV Space**.

*   **Coordinate System:** OpenCV Convention. Both the camera frame (+Z forward) and the tag frame (+Z into plane) adhere to this standard.
*   **Position (`position`):** `[x, y, z]` in meters.
*   **Rotation (`rotation_quaternion`):**
    *   **Format:** **`[w, x, y, z]` (Scalar-First)** in all exported files and throughout the entire pipeline.

### 3.2 Detection Metadata
*   **Active Size (`tag_size_mm`):** The physical edge length of the **black border** only (excluding margin/quiet zone) in millimeters.
*   **PPM (Pixels Per Module):** A metric for visual resolution.
    \\[
    PPM = \frac{f_{px} \cdot \text{size}_m}{Z_{depth} \cdot \text{grid\_size}}
    \\]
    Where `grid_size` is the number of bits (e.g., 8 for `tag36h11`).
*   **Physics Conditions:**
    *   `velocity`: Camera velocity vector [vx, vy, vz] in m/s.
    *   `shutter_time_ms`: Exposure duration.
    *   `rolling_shutter_ms`: Sensor readout duration.
    *   `fstop`: Lens aperture.

### 3.3 Manifests & Provenance
#### `provenance.json`
The master manifest for the dataset. It maps every `image_id` to its full `SceneRecipe`.
- **Intrinsics:** Stored in `provenance.json` and duplicated in records.
- **K Matrix:** 3x3 matrix `[[fx, 0, cx], [0, fy, cy], [0, 0, 1]]`.
- **Principal Point:** `(cx, cy)`, typically image center.

### 3.4 Keypoint Convention
- **Ordering:** Row-major, zero-indexed.
- **Topology:** Continuous numbering starting from the Top-Left corner.
- **Winding:** All projected 2D corners follow a **Strictly Clockwise (CW)** winding order in the image plane (Y-down).
- **Sentinel Value:** Out-of-frame or behind-camera keypoints are filled with `(-1.0, -1.0)` to preserve index alignment. Use `is_sentinel_keypoint()` or filter before passing to calibration routines.

### 3.5 Board Definition (BOARD Records)
`BOARD` detection records carry a typed `board_definition` field (`BoardDefinition` Pydantic model) that fully describes the resolved board geometry:

| Field | Description |
|-------|-------------|
| `type` | `charuco` or `aprilgrid` |
| `rows`, `cols` | Grid dimensions |
| `square_size_mm` | Checkerboard square edge length (mm) |
| `marker_size_mm` | Marker edge length (mm) |
| `dictionary` | Tag family / ArUco dictionary name |
| `total_keypoints` | Expected number of calibration keypoints |
| `spacing_ratio` | AprilGrid spacing ratio (required for `aprilgrid`, `null` for `charuco`) |

This makes `rich_truth.json` self-describing — downstream calibration scripts can reconstruct the 3D object points directly from the record without external configuration.

---

### Physical Size vs. Annotated Corners
*   **`size_meters`**: Defines the **outer edge** of the entire physical asset (including white margin).
*   **Annotated Corners**: Represent the **outer edge of the black border** only. 

The relationship is determined by `margin_bits`. For a tag with \\(N\\) bits and a margin of \\(M\\) bits, the annotated corners are located at a scale of \\(N / (N + 2M)\\) relative to the physical center.
