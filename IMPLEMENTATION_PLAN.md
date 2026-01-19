# Implementation Plan: render-tag

**Objective**: Build a robust, offline 3D synthetic data generation pipeline for AprilTag detection using blenderproc.
**Philosophy**: Separation of Concerns. The CLI manages the "Job"; the Script manages the "Physics"; the Math manages the "Truth".

## Phase 1: Configuration & Contracts (The "Brain")
Before spawning Blender, we must strictly define what we are asking it to do.

### 1.1. Define the Configuration Schema (`src/render_tag/config.py`)
- [x] Create a `GenConfig` Pydantic model (v2) to act as the single source of truth.
- [x] Fields to include:
    - `dataset`: output_dir, seed (int).
    - `camera`: resolution (w, h), fov (float), samples_per_scene (int), intrinsics (K matrix or focal length/sensor size).
    - [x] **Full Intrinsics Support**: Support all camera intrinsics supported by Blender (K matrix, principal point, distortion coefficients).
    - `tag`: family (enum: "tag36h11"), size_meters (float), texture_path (Path).
    - `scene`: lighting_intensity (min/max), background_hdri (Path or None).
    - `physics`: drop_height (float), scatter_radius (float).
- [x] Implement `load_config(path: Path) -> GenConfig` with strict YAML validation.
- [x] Agent Instruction: "Ensure the config model forbids invalid states (e.g., negative resolution)."

### 1.2. Define the Output Schema
- [x] Define the `TagDetection` dataclass matching the Locus CSV format (image_id, tag_id, 4x corners).
- [x] Define the `COCOAnnotation` structure for instance segmentation.

## Phase 2: The Blender Driver (The "Engine")
This code runs INSIDE the Blender process. It has access to `bpy` and `bproc` but NO access to the CLI state.

### 2.1. Driver Skeleton (`src/render_tag/scripts/blender_main.py`)
- [ ] Implement `argparse` to receive the path to the serialized `config.json` (passed by the CLI).
- [ ] Initialize `bproc.init()`.
- [ ] Create the main loop: `setup_scene` -> `simulate_physics` -> `sample_cameras` -> `render` -> `write_data`.

### 2.2. Asset Loader
- [ ] Implement `load_tag_asset()`:
    - Create a simple Plane primitive.
    - Map the specific AprilTag texture (from `assets/`) to the UVs strictly.
    - **Crucial**: Store the local 3D coordinates of the 4 corners (e.g., `[(-s, s, 0), (s, s, 0), ...]`) in a known order.

### 2.3. Scene Construction
- [ ] **Lighting**: Implement randomized lighting sampling (HDRI environment + random Point lights).
- [ ] **Backgrounds**: Use `bproc.world.set_world_background_hdr_img` for realistic reflections.
- [ ] **Physics**:
    - Create a passive floor plane.
    - Set the Tag object to active rigid body.
    - Implement a "Scatter" function: Randomize tag position/rotation above the floor.
    - Call `bproc.object.simulate_physics_and_fix_final_poses()`.

### 2.4. Camera Sampling
- [ ] Use `bproc.sampler.part_sphere` to generate camera poses looking at the scene center.
- [ ] Filter poses: Reject cameras that are "under the floor" or too close.

## Phase 3: The Orchestrator (The "Manager")
This runs in the standard system Python environment.

### 3.1. CLI Implementation (`src/render_tag/cli.py`)
- [ ] Implement the `generate` command using `typer`.
- [ ] Workflow:
    - Load and validate `config.yaml`.
    - Serialize the validated config to a temp `job_config.json`.
    - Construct the command: `blenderproc run src/.../blender_main.py --config job_config.json`.
    - Execute via `subprocess.run` (stream stdout to console for progress).

### 3.2. Error Handling
- [ ] Check for `blenderproc` installation availability.
- [ ] Handle subprocess exit codes (e.g., if Blender crashes, the CLI should report "Rendering Failed").

## Phase 4: Critical Math & Data Export (The "Truth")
This is the most fragile part. It requires precise Coordinate System conversions.

### 4.1. Corner Projection Logic (Inside Driver)
- [ ] Do NOT use Bounding Boxes. They are axis-aligned and useless for corner regression.
- [ ] Implement `get_projected_corners(tag_obj, camera_matrix)`:
    - Retrieve the 4 local vertices of the Tag plane.
    - Transform them to World Space (using `tag_obj.get_local2world_mat()`).
    - Project them to Image Space (using `bproc.camera.project_to_image()`).
- [ ] Visibility Check:
    - Implement a raycast or depth-check to ensure the corners are not occluded by other objects (or the tag isn't flipped upside down facing away).

### 4.2. Sorting & Formatting
- [ ] The "Clockwise Rule":
    - Ensure the corners are strictly ordered: Top-Left, Top-Right, Bottom-Right, Bottom-Left.
    - Note: Since we know the local vertex order of the plane, this should be preserved by the projection. Verify this assumption explicitly in code.

### 4.3. Writers
- [ ] **CSV Writer**: Append row: `filename, id, x1, y1, x2, y2, x3, y3, x4, y4`.
- [ ] **COCO Writer**: Use `bproc.writer.write_coco_annotations` for the segmentation masks, mapping the Tag object ID to the COCO category.

## Phase 5: Verification & Quality Assurance
Ensure the data is actually usable for ML.

### 5.1. Visual Debugging Tool
- [ ] Create a small helper `tests/debug_viz.py`.
- [ ] Logic: Read the generated image and the CSV. Draw lines connecting the 4 corners.
- [ ] Success Metric: The drawn lines must perfectly align with the visual tag borders.

### 5.2. Integration Test
- [ ] Write a `pytest` case that runs the full pipeline with `samples=1` and `resolution=[100,100]`.
- [ ] Assertions:
    - Output directory exists.
    - `tags.csv` has exactly 1 row.
    - Values in CSV are within image bounds (0-100).

## Phase 6: Advanced Realism (The "Chaos")
Enhance the dataset robustness through randomization.

### 6.1. Domain Randomization
- [ ] Implement random MATERIAL properties for the tag (glossiness, roughness) to simulate different print qualities.
- [ ] Randomize floor materials (textures from a pool of PBR materials).
- [ ] Randomize lights and shadows.


### 6.2. Parameter Randomization
- [ ] **Motion Blur**: Simulate camera movement or tag movement during exposure.
- [ ] **Depth of Field**: Randomize focal distance and f-stop to create realistic bokeh/blur.
- [ ] **Post-processing**: Add noise, compression artifacts, and color jittering.