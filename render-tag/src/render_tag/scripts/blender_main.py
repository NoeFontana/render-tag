import blenderproc as bproc

"""
BlenderProc main driver script for render-tag synthetic data generation.

This script runs INSIDE the Blender process and has access to bpy and bproc.
It is invoked by the CLI via: blenderproc run blender_main.py --config <path>
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# ruff: noqa: E402

# Add the src directory to sys.path to allow absolute imports from the render_tag package
# This is required because the package is not installed in the Blender python environment
sys.path.append(str(Path(__file__).resolve().parents[2]))
# (Relies on package being installed or PYTHONPATH set)

# Try to import bpy but don't fail if not in Blender
try:
    import bpy
except ImportError:
    bpy = None  # type: ignore

# Now we can import using the full package path
from render_tag.common.constants import TAG_BIT_COUNTS
from render_tag.data_io.types import DetectionRecord
from render_tag.data_io.writers import COCOWriter, CSVWriter
from render_tag.scripts.camera import sample_camera_poses, set_camera_intrinsics
from render_tag.scripts.compositor import compose_scene
from render_tag.scripts.projection import (
    check_tag_facing_camera,
    check_tag_visibility,
    is_tag_sufficiently_visible,
    project_corners_to_image,
)
from render_tag.scripts.scene import (
    setup_background,
    setup_lighting,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments passed by the CLI."""
    parser = argparse.ArgumentParser(description="BlenderProc render-tag driver")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the serialized config JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for rendered data",
    )
    parser.add_argument(
        "--renderer-mode",
        choices=["cycles", "workbench", "eevee"],
        default="cycles",
        help="Rendering engine: cycles (quality), workbench (instant), eevee (fast)",
    )
    return parser.parse_args()


def load_config_json(config_path: Path) -> dict:
    """Load the config from a JSON file serialized by the CLI."""
    with open(config_path) as f:
        return json.load(f)


def setup_scene(config: dict) -> None:
    """Initialize the scene with background and basic setup."""
    # Set world background if HDRI is provided
    hdri_path = config.get("scene", {}).get("background_hdri")
    if hdri_path and Path(hdri_path).is_file():
        setup_background(Path(hdri_path))
    else:
        # Pure white background for maximum contrast (matches reference image style)
        if bpy:
            bpy.context.scene.world.use_nodes = True
            bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
            if bg_node:
                bg_node.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
                bg_node.inputs[1].default_value = 1.0


def render_scene(output_dir: Path, scene_idx: int, cam_idx: int) -> Path:
    """Render the current scene and save the image."""
    # Set output path
    image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"

    # Render using blenderproc
    data = bproc.renderer.render()

    # Save the rendered image
    image_path = output_dir / "images" / f"{image_name}.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)

    # BlenderProc returns images as numpy arrays
    if "colors" in data and len(data["colors"]) > 0:
        from PIL import Image

        img_array = data["colors"][0]
        img = Image.fromarray(img_array.astype(np.uint8))
        img.save(str(image_path))

    return image_path


def get_valid_detections(
    tag_objects: list,
    min_visible_corners: int = 3,
    require_facing: bool = True,
) -> list[tuple]:
    """Get detections for visible, properly-facing tags.

    Args:
        tag_objects: List of tag mesh objects
        min_visible_corners: Minimum corners visible in frame
        require_facing: Whether to require tag facing camera

    Returns:
        List of (tag_obj, corners_2d) tuples for valid detections
    """
    valid_detections = []

    for tag_obj in tag_objects:
        # Check visibility
        if not check_tag_visibility(tag_obj, min_visible_corners):
            continue

        # Check if facing camera (not flipped away)
        if require_facing and not check_tag_facing_camera(tag_obj):
            continue

        # Get projected corners
        corners_2d = project_corners_to_image(tag_obj)
        if corners_2d is None:
            continue

        valid_detections.append((tag_obj, corners_2d))

    return valid_detections


def main() -> int:
    """Main entry point for the BlenderProc driver."""
    args = parse_args()

    # Load configuration
    config = load_config_json(args.config)
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize BlenderProc
    bproc.init()

    # Get config sections
    camera_config = config.get("camera", {})
    tag_config = config.get("tag", {})
    scene_config = config.get("scene", {})
    physics_config = scene_config.get("physics", config.get("physics", {}))
    _board_config = config.get("board", {})
    scenario_config = config.get("scenario", {})

    # Set camera intrinsics
    set_camera_intrinsics(camera_config)

    # Get resolution for COCO writer and visibility check
    resolution = camera_config.get("resolution", [640, 480])

    # Initialize writers
    csv_writer = CSVWriter(output_dir / "tags.csv")
    coco_writer = COCOWriter(output_dir)

    # Add tag families to COCO categories
    tag_families = scenario_config.get("tag_families", ["tag36h11"])
    # Also support legacy single family config
    if "family" in tag_config:
        tag_families = [tag_config["family"]]

    for fam in tag_families:
        coco_writer.add_category(fam)

    # Get bit count for the FIRST family (simplified assumption for mixed scenes)
    # Ideally should check per tag, but this is a reasonable heuristic for filtering
    min_bits = TAG_BIT_COUNTS.get(tag_families[0], 36)

    # Number of scenes to generate
    num_scenes = config.get("dataset", {}).get("num_scenes", 1)
    samples_per_scene = camera_config.get("samples_per_scene", 10)

    total_images = 0
    total_detections = 0

    for scene_idx in range(num_scenes):
        # Clean scene for new iteration
        bproc.clean_up()

        # Configure renderer mode for fast dev iteration (re-apply after clean_up)
        renderer_mode = getattr(args, "renderer_mode", "cycles")
        if renderer_mode == "workbench":
            # Ultra-fast wireframe/flat shading for scene composition checks
            bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
            # Enable textures in workbench
            bpy.data.scenes["Scene"].display.shading.light = "FLAT"
            bpy.data.scenes["Scene"].display.shading.color_type = "TEXTURE"
            bpy.context.scene.render.resolution_percentage = 100
            print(f"[SCENE {scene_idx}] Using Workbench renderer with FLAT shading")
        elif renderer_mode == "eevee":
            # Fast rasterized preview (Blender 4.2+ uses BLENDER_EEVEE_NEXT)
            try:
                bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
            except Exception:
                bpy.context.scene.render.engine = "BLENDER_EEVEE"
            bpy.context.scene.render.resolution_percentage = 100
            print(f"[SCENE {scene_idx}] Using Eevee renderer at 100% resolution")

        set_camera_intrinsics(camera_config)

        # Setup scene background
        setup_scene(config)

        # Compose the scene (tags, layout, physics)
        tag_objects, _layout_objects, layout_mode = compose_scene(
            scene_idx=scene_idx,
            tag_config=tag_config,
            scenario_config=scenario_config,
            scene_config=scene_config,
            physics_config=physics_config,
            tag_families=tag_families,
        )

        # Get flying flag for camera sampling
        is_flying = scenario_config.get("flying", False)
        sampling_mode = camera_config.get(
            "sampling_mode", scenario_config.get("sampling_mode", "random")
        )

        # Setup lighting
        lighting_config = scene_config.get("lighting", {})
        setup_lighting(
            intensity_min=lighting_config.get("intensity_min", 50),
            intensity_max=lighting_config.get("intensity_max", 500),
            radius_min=lighting_config.get("radius_min", 0.0),
            radius_max=lighting_config.get("radius_max", 0.0),
        )

        # Sample camera poses with visibility guarantee
        # We need `samples_per_scene` VALID images
        valid_samples = 0
        attempts = 0
        max_total_attempts = samples_per_scene * 50

        while valid_samples < samples_per_scene and attempts < max_total_attempts:
            attempts += 1

            # Sample ONE pose
            # For board layouts, look exactly at the center of the board
            look_target = (
                [0, 0, 0]
                if layout_mode in ("cb", "aprilgrid", "plain")
                else ([0, 0, 0.5] if is_flying else [0, 0, 0.05])
            )
            poses = sample_camera_poses(
                num_samples=1,
                look_at_point=look_target,
                min_distance=camera_config.get("min_distance", 0.5),
                max_distance=camera_config.get("max_distance", 2.0),
                elevation=camera_config.get("elevation"),
                azimuth=camera_config.get("azimuth"),
                min_elevation=camera_config.get("min_elevation", 0.3),
                max_elevation=camera_config.get("max_elevation", 0.9),
                sampling_mode=sampling_mode,
                sample_idx=valid_samples,
                total_samples=samples_per_scene,
            )
            if not poses:
                continue

            pose = poses[0]

            # Set camera pose directly via bpy to check visibility without adding keyframe
            import mathutils

            bpy.context.scene.camera.matrix_world = mathutils.Matrix(pose)
            bpy.context.view_layer.update()  # CRITICAL: Update scene to reflect new pose

            # Check visibility
            visible_tags_count = 0
            for tag_obj in tag_objects:
                if is_tag_sufficiently_visible(tag_obj, min_area_pixels=min_bits):
                    visible_tags_count += 1

            if visible_tags_count > 0:
                # Valid! Add the pose to the render queue
                bproc.camera.add_camera_pose(pose)
                valid_samples += 1
                total_images += 1
                total_detections += visible_tags_count
                msg = (
                    f"{scene_idx}.{valid_samples}: {samples_per_scene} "
                    f"(dist={np.linalg.norm(pose[:3, 3]):.2f}m) - {visible_tags_count} tags"
                )
                print(msg)
            else:
                if attempts % 100 == 0:
                    print(
                        f"  [!] Attempt {attempts}/{max_total_attempts}: "
                        "Still looking for visible pose..."
                    )
        # Render ALL VALID camera poses at once (frames)
        # BlenderProc renders all poses added via bproc.camera.add_camera_pose
        rendered_data = bproc.renderer.render() if valid_samples > 0 else {}

        # Process each rendered frame
        for cam_idx in range(valid_samples):
            image_name = f"scene_{scene_idx:04d}_cam_{cam_idx:04d}"
            image_path = output_dir / "images" / f"{image_name}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)

            # Save frame from rendered data
            if "colors" in rendered_data and len(rendered_data["colors"]) > cam_idx:
                from PIL import Image

                img_array = rendered_data["colors"][cam_idx]
                Image.fromarray(img_array.astype(np.uint8)).save(str(image_path))

            # Add image to COCO dataset
            coco_image_id = coco_writer.add_image(
                file_name=f"images/{image_path.name}",
                width=resolution[0],
                height=resolution[1],
            )

            # CRITICAL: Manually update camera matrix to match this frame for visibility writing
            # bproc.camera.get_camera_pose(frame) returns the correct matrix
            frame_pose = bproc.camera.get_camera_pose(cam_idx)
            bpy.context.scene.camera.matrix_world = mathutils.Matrix(frame_pose)
            bpy.context.view_layer.update()

            # Get valid detections (visible, facing camera)
            valid_detections = get_valid_detections(tag_objects)

            # Write detections
            for tag_obj, corners_2d in valid_detections:
                # tag_obj is a bproc.types.MeshObject, use its blender_obj for custom properties
                blender_obj = tag_obj.blender_obj
                tag_id = blender_obj.get("tag_id", 0)
                tag_fam = blender_obj.get("tag_family", tag_families[0])

                # Write to CSV
                detection = DetectionRecord(
                    image_id=image_name,
                    tag_id=tag_id,
                    tag_family=tag_fam,
                    corners=corners_2d,
                )
                csv_writer.write_detection(detection, width=resolution[0], height=resolution[1])

                # Write to COCO
                coco_writer.add_annotation(
                    image_id=coco_image_id,
                    category_id=coco_writer._category_map.get(tag_fam, 1),
                    corners=corners_2d,
                    detection=detection,
                    width=resolution[0],
                    height=resolution[1],
                )

    # Save COCO annotations
    coco_writer.save()

    print(f"✓ Generated {total_images} images with {total_detections} detections")
    print(f"  Output: {output_dir}")
    print(f"  CSV: {output_dir / 'tags.csv'}")
    print(f"  COCO: {output_dir / 'annotations.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
