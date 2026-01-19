import blenderproc as bproc

"""
BlenderProc main driver script for render-tag synthetic data generation.

This script runs INSIDE the Blender process and has access to bpy and bproc.
It is invoked by the CLI via: blenderproc run blender_main.py --config <path>
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

import numpy as np

# ruff: noqa: E402

# Add the src directory to sys.path to allow absolute imports from the render_tag package
scripts_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(scripts_dir))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Try to import bpy but don't fail if not in Blender
try:
    import bpy
except ImportError:
    bpy = None  # type: ignore

# Now we can import using the full package path
from render_tag.scripts.assets import create_tag_plane, get_tag_texture_path
from render_tag.scripts.camera import sample_camera_poses, set_camera_intrinsics
from render_tag.scripts.projection import (
    check_tag_facing_camera,
    check_tag_visibility,
    is_tag_sufficiently_visible,
    project_corners_to_image,
)
from render_tag.scripts.scene import (
    create_floor,
    setup_background,
    setup_lighting,
    create_flying_layout,
)
from render_tag.data_io.writers import COCOWriter, CSVWriter
from render_tag.data_io.types import DetectionRecord

# Bit counts for each tag family (used for minimum pixel area calculation)
TAG_BIT_COUNTS = {
    "tag36h11": 36,
    "tag36h10": 36,
    "tag25h9": 25,
    "tag16h5": 16,
    "tagCircle21h7": 21,
    "tagCircle49h12": 49,
    "tagCustom48h12": 48,
    "tagStandard41h12": 41,
    "tagStandard52h13": 52,
    "DICT_4X4_50": 16,
    "DICT_4X4_100": 16,
    "DICT_4X4_250": 16,
    "DICT_6X6_1000": 36,
    "DICT_7X7_50": 49,
    "DICT_7X7_100": 49,
    "DICT_7X7_250": 49,
    "DICT_7X7_1000": 49,
    "DICT_ARUCO_ORIGINAL": 25,
}


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
        help="Rendering engine: cycles (quality), workbench (instant wireframe), eevee (fast preview)",
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
    if hdri_path and Path(hdri_path).exists():
        setup_background(Path(hdri_path))


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

    # Configure renderer mode for fast dev iteration
    renderer_mode = getattr(args, "renderer_mode", "cycles")
    if renderer_mode == "workbench":
        # Ultra-fast wireframe/flat shading for scene composition checks
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        bpy.data.scenes["Scene"].display.shading.light = "FLAT"
        bpy.context.scene.render.resolution_percentage = 25
        print("[FAST] Using Workbench renderer at 25% resolution")
    elif renderer_mode == "eevee":
        # Fast rasterized preview (Blender 4.2+ uses BLENDER_EEVEE_NEXT)
        try:
            bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        except Exception:
            bpy.context.scene.render.engine = "BLENDER_EEVEE"
        bpy.context.scene.render.resolution_percentage = 50
        print("[FAST] Using Eevee renderer at 50% resolution")
    # else: use default Cycles for quality rendering

    # Get config sections
    # Get config sections
    camera_config = config.get("camera", {})
    tag_config = config.get("tag", {})
    scene_config = config.get("scene", {})
    physics_config = config.get("physics", {})
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
        set_camera_intrinsics(camera_config)

        # Setup scene background
        setup_scene(config)

        # Get scenario flags
        is_flying = scenario_config.get("flying", False)
        sampling_mode = scenario_config.get("sampling_mode", "random")

        # Create floor if NOT flying and NOT checkerboard
        layout_mode = scenario_config.get("layout", "plain")
        if not is_flying and layout_mode not in ("cb", "aprilgrid"):
            create_floor()

        # Determine number of tags for this scene
        grid_size = scenario_config.get("grid_size", [6, 6])

        if layout_mode == "cb":
            # ChArUco board: tags go in alternating (white) squares
            # For an MxN board, approx M*N/2 white squares (ceiling)
            cols, rows = grid_size[0], grid_size[1]
            total_squares = cols * rows
            num_tags = (total_squares + 1) // 2  # Ceiling division
        elif layout_mode == "aprilgrid":
            # AprilGrid/Kalibr: tags in every cell
            cols, rows = grid_size[0], grid_size[1]
            num_tags = cols * rows
        else:
            import random
            tags_range = scenario_config.get("tags_per_scene", [1, 5])
            num_tags = random.randint(tags_range[0], tags_range[1])
            cols, rows = None, None

        # Create tag objects
        tag_objects = []
        tag_size = tag_config.get("size_meters", 0.1)
        texture_base_path = tag_config.get("texture_path")

        for i in range(num_tags):
            import random
            family = random.choice(tag_families)
            texture_path = get_tag_texture_path(family, texture_base_path, tag_id=i)

            # Create tag with random ID (handled by texture loader usually, but here just reuse)
            # In a real pipeline, we'd select specific IDs.
            tag_obj = create_tag_plane(tag_size, texture_path, family, tag_id=i)

            # Set custom properties for ground truth
            tag_obj.blender_obj["tag_id"] = i  # Placeholder ID, ideally from texture
            tag_obj.blender_obj["tag_family"] = family

            tag_objects.append(tag_obj)

        # Apply layout
        square_size = scenario_config.get("square_size", 0.12)
        marker_margin = scenario_config.get("marker_margin", 0.01)
        corner_size = scenario_config.get("corner_size", 0.02)
        tag_spacing = scenario_config.get("tag_spacing", 0.05)

        # Import layouts module here to avoid circular imports or early failure
        from render_tag.scripts.layouts import apply_layout

        if is_flying:
            # Flying mode: ignore layout and scatter in volume
            create_flying_layout(
                tag_objects, volume_size=tag_config.get("scatter_radius", 0.5) * 2
            )
        else:
            # Standard mode: apply layout and settle with physics
            layout_objects = apply_layout(
                tag_objects=tag_objects,
                layout_mode=layout_mode,
                spacing=tag_spacing,
                square_size=square_size,
                marker_margin=marker_margin,
                corner_size=corner_size,
                center=(0, 0, 0),
                cols=cols,
                rows=rows,
            )

            # For checkerboard or aprilgrid, create a white board background
            if layout_mode in ("cb", "aprilgrid"):
                board_width = cols * square_size
                board_height = rows * square_size

                # Create a simple plane for the board
                board = bproc.object.create_primitive("PLANE")
                board.set_location([0, 0, -0.001])  # Slightly below tags
                board.set_scale([board_width / 2, board_height / 2, 1])
                board.persist_transformation_into_mesh()

                # White material
                mat = bpy.data.materials.new(name="BoardWhite")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
                    bsdf.inputs["Roughness"].default_value = 0.8
                board.blender_obj.data.materials.clear()
                board.blender_obj.data.materials.append(mat)
                board.enable_rigidbody(active=False)
                layout_objects.append(board)

            # Setup Z height and simulate physics
            drop_height = physics_config.get("drop_height", 0.1)
            for obj in tag_objects + layout_objects:
                obj.enable_rigidbody(active=True)
                loc = obj.get_location()
                obj.set_location([loc[0], loc[1], drop_height])

            bproc.object.simulate_physics_and_fix_final_poses(
                min_simulation_time=1,
                max_simulation_time=2,
                check_object_interval=1,
            )

        # Setup lighting
        lighting_config = scene_config.get("lighting", {})
        setup_lighting(
            intensity_min=lighting_config.get("intensity_min", 50),
            intensity_max=lighting_config.get("intensity_max", 500),
        )

        # Sample camera poses with visibility guarantee
        # We need `samples_per_scene` VALID images
        valid_samples = 0
        attempts = 0
        max_total_attempts = samples_per_scene * 50

        while valid_samples < samples_per_scene and attempts < max_total_attempts:
            attempts += 1

            # Sample ONE pose
            poses = sample_camera_poses(
                num_samples=1,
                look_at_point=[0, 0, 0.5] if is_flying else [0, 0, 0.05],
                min_distance=camera_config.get("min_distance", 0.5),
                max_distance=camera_config.get("max_distance", 2.0),
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
                print(
                    f"  [✓] Sample {valid_samples}/{samples_per_scene} (dist={np.linalg.norm(pose[:3, 3]):.2f}m) - {visible_tags_count} tags visible"
                )
            else:
                if attempts % 100 == 0:
                    print(
                        f"  [!] Attempt {attempts}/{max_total_attempts}: Still looking for visible pose..."
                    )

        # Render from each camera pose
        for cam_idx in range(valid_samples):
            # Render
            image_path = render_scene(output_dir, scene_idx, cam_idx)
            image_name = image_path.stem

            # Add image to COCO dataset
            coco_image_id = coco_writer.add_image(
                file_name=f"images/{image_path.name}",
                width=resolution[0],
                height=resolution[1],
            )

            # Get valid detections (visible, facing camera)
            # We reuse the visibility check but need exact corners for writing
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
                csv_writer.write_detection(
                    detection, width=resolution[0], height=resolution[1]
                )

                # Write to COCO
                coco_writer.add_annotation(
                    image_id=coco_image_id,
                    category_id=coco_writer._category_map.get(tag_fam, 1),
                    corners=corners_2d,
                    tag_id=tag_id,
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
