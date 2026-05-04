# Mathematical Frustum Culling for Occluders

## 1. Objective
Ensure shadow-casting occluders (plates) are mathematically guaranteed to be out of the camera's view frustum, thereby only casting shadows onto the tag without directly blocking the tag from the camera's perspective.

## 2. Approach

1.  **True Frustum Intersection (SAT):**
    *   Instead of discrete ray-checks, we will project the plate's 3D corners onto the camera's 2D image plane using the camera's intrinsic ($K$) and extrinsic ($T_{wc}$) matrices.
    *   We will clip the 3D polygon against the camera's near plane ($z > 0$) to prevent projection artifacts.
    *   We will use the Separating Axis Theorem (SAT) in 2D to check if the projected convex polygon intersects the image boundary box ($[0, W] \times [0, H]$).
2.  **Sun-Ray Sliding:**
    *   If an occluder intersects the camera frustum, we do not reject the sample immediately.
    *   Because directional lights (SUN) cast parallel rays, sliding the occluder along the sun-ray vector ($P_{new} = P_{old} + \Delta h \cdot \frac{\vec{S}}{S_z}$) perfectly preserves the shadow cast on the $Z=0$ plane.
    *   Since cameras typically point downwards (elevation > 0), sliding the occluder *upwards* along the sun ray guarantees it will eventually exit the camera frustum.
    *   We will iteratively slide intersecting plates upwards in small increments (e.g., 5cm) until they clear all camera frustums.

## 3. Key Files & Context
*   `src/render_tag/generation/strategy/occluder.py`: Core logic for plate placement. Needs the sliding loop and the SAT check.
*   `src/render_tag/generation/compiler.py`: Handles `_sample_camera_recipes` before `occluder_strategy.sample_pose`. We need to pass the full camera recipes (or at least their $K$ and $T_{wc}$ matrices) to the occluder strategy.
*   `src/render_tag/core/schema/recipe.py`: `CameraRecipe` and `ObjectRecipe` structures.

## 4. Implementation Steps

1.  **Refactor Compiler Argument Passing:**
    *   Modify `OccluderStrategy.sample_pose` signature to accept a list of `CameraRecipe` objects instead of just `camera_positions`.
    *   Update `SceneCompiler.compile_scene` to pass `recipe.cameras`.
2.  **Implement Frustum Check Mathematics:**
    *   Add `_is_plate_in_frustum(plate, cam_recipe)` to `occluder.py`.
    *   Implement 3D-to-2D projection with near-plane clipping (Sutherland-Hodgman style for the $z=0$ plane).
    *   Implement 2D SAT intersection between the projected polygon and the image rectangle.
3.  **Implement Sun-Ray Sliding Loop:**
    *   In `OccluderStrategy.sample_pose`, replace the `MAX_PLACEMENT_ATTEMPTS` retry loop with a guaranteed sliding loop.
    *   Generate the initial plates at the sampled height $h$.
    *   While any plate intersects any camera frustum, increment the height of *all* plates in the pattern by $\Delta h = 0.05m$ along the sun ray.
    *   Cap sliding to a reasonable maximum (e.g., 50 iterations / $2.5m$) to prevent infinite loops on pathological edge cases.

## 5. Verification & Testing
*   Update `test_occluder_strategy.py` to test the new sliding logic and ensure `location[2]` increases when a camera looks directly at the plate.
*   Verify that `viz recipe` and actual renders (via `uv run render-tag generate`) show occluders successfully dodging the camera while maintaining hard shadows on the tags.