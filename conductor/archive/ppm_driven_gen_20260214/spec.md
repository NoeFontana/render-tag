# Specification: PPM-Driven Generation

## Overview
Implement Pixels Per Module (PPM)-Driven Generation to linearize the difficulty of synthetic datasets. By sampling in PPM space instead of pure distance space, the generator will provide uniform coverage across "easy" (high PPM), "medium," and "hard" (low PPM) scenarios. This replaces or overrides manual distance min/max constraints with goal-oriented visual resolution targets.

## Functional Requirements

### 1. Schema Update (The Contract)
- Implement `PPMConstraint` model in `src/render_tag/core/config.py`.
- Fields: `min_ppm` (float), `max_ppm` (float), `sampling_distribution` (default: `uniform`).
- Update `CameraConfig` (or relevant sampling config) to include an optional `ppm_constraint`.
- Add a validator: If `ppm_constraint` is present, it takes precedence over manual `min_distance` and `max_distance`.

### 2. Math Solver (The Kernel)
- Implement `calculate_ppm(distance_m, tag_size_m, focal_length_px, tag_grid_size)` in `src/render_tag/generation/projection_math.py`.
- Implement `solve_distance_for_ppm(target_ppm, tag_size_m, focal_length_px, tag_grid_size)` in `src/render_tag/generation/projection_math.py`.
- Use a lookup table for `tag_grid_size` based on tag family (e.g., 8 for `tag36h11`, 9 for `tagStandard41h12`).

### 3. Generator Logic (Sampling Strategy)
- Modify `SceneRecipeBuilder.build_cameras` in `src/render_tag/generation/builder.py` to support PPM sampling.
- If `ppm_constraint` is active:
    1. Sample a random `target_ppm` from the specified range.
    2. Solve for `distance_m` using the camera's effective focal length and the tag's physical size.
    3. Use the calculated distance for camera pose sampling.
- Implement safety clips: Discard and resample if the calculated distance is outside the camera's physical clip planes.

### 4. Output & Auditing
- Calculate and persist the *actual* exact PPM for every detection.
- **CSV Export:** Add a `ppm` column to `tags.csv`.
- **Rich Truth:** Include `meta_ppm` in `rich_truth.json`.
- **Metadata:** Include PPM in individual image sidecars (`*_meta.json`).
- **Audit:** Update `manifest.json` and the audit pipeline to report on PPM distribution statistics.

## Acceptance Criteria
- [ ] Users can define `ppm_constraint` in the YAML configuration.
- [ ] The generator correctly calculates camera distances to meet target PPM.
- [ ] Generated datasets show a uniform distribution of PPM across the requested range.
- [ ] `tags.csv` and `rich_truth.json` contain accurate PPM metadata for every tag.
- [ ] The audit dashboard displays PPM distribution metrics.

## Out of Scope
- Scaling the tag physically to achieve PPM (Variable Size).
- Non-uniform PPM distributions (e.g., Gaussian) unless specifically requested later.
