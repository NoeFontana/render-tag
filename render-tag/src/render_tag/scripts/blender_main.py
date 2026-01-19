import blenderproc as bproc
"""
BlenderProc main driver script for render-tag synthetic data generation.

This script runs INSIDE the Blender process and has access to bpy and bproc.
It is invoked by the CLI via: blenderproc run blender_main.py --config <path>

Usage:
    blenderproc run blender_main.py --config job_config.json --output output/dataset_01
"""

import argparse
import json
import sys
import os
from pathlib import Path

# Add the current directory to sys.path to allow imports from sibling files
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import bpy but don't fail if not in Blender
try:
    import bpy
except ImportError:
    bpy = None  # type: ignore

from assets import create_tag_plane, get_tag_texture_path
from camera import sample_camera_poses, set_camera_intrinsics
from projection import check_tag_facing_camera, check_tag_visibility, project_corners_to_image
from scene import create_floor, scatter_tags, setup_background, setup_lighting
from writers import COCOWriter, CSVWriter, DetectionRecord


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
        import numpy as np
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
    physics_config = config.get("physics", {})
    
    # Set camera intrinsics
    set_camera_intrinsics(camera_config)
    
    # Get resolution for COCO writer
    resolution = camera_config.get("resolution", [640, 480])
    
    # Initialize writers
    csv_writer = CSVWriter(output_dir / "tags.csv")
    coco_writer = COCOWriter(output_dir)
    
    # Add tag family as category
    tag_family = tag_config.get("family", "tag36h11")
    category_id = coco_writer.add_category(tag_family)
    
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
        
        # Create floor for physics
        floor = create_floor()
        
        # Create tag asset
        tag_size = tag_config.get("size_meters", 0.1)
        texture_path = get_tag_texture_path(tag_family, tag_config.get("texture_path"))
        
        tag_obj = create_tag_plane(tag_size, texture_path, tag_family)
        tag_objects = [tag_obj]
        
        # Setup lighting
        lighting_config = scene_config.get("lighting", {})
        setup_lighting(
            intensity_min=lighting_config.get("intensity_min", 50),
            intensity_max=lighting_config.get("intensity_max", 500),
        )
        
        # Scatter tags and simulate physics
        drop_height = physics_config.get("drop_height", 1.5)
        scatter_radius = physics_config.get("scatter_radius", 0.5)
        scatter_tags(tag_objects, drop_height, scatter_radius)
        
        # Simulate physics
        bproc.object.simulate_physics_and_fix_final_poses(
            min_simulation_time=1,
            max_simulation_time=4,
            check_object_interval=1,
        )
        
        # Sample camera poses
        camera_poses = sample_camera_poses(
            num_samples=samples_per_scene,
            look_at_point=[0, 0, 0],
            min_distance=0.5,
            max_distance=2.0,
        )
        
        # Render from each camera pose
        for cam_idx, pose in enumerate(camera_poses):
            bproc.camera.add_camera_pose(pose)
            
            # Render
            image_path = render_scene(output_dir, scene_idx, cam_idx)
            image_name = image_path.stem
            total_images += 1
            
            # Add image to COCO dataset
            coco_image_id = coco_writer.add_image(
                file_name=f"images/{image_path.name}",
                width=resolution[0],
                height=resolution[1],
            )
            
            # Get valid detections (visible, facing camera)
            valid_detections = get_valid_detections(tag_objects)
            
            # Write detections
            for tag_obj, corners_2d in valid_detections:
                # tag_obj is a bproc.types.MeshObject, use its blender_obj for custom properties
                blender_obj = tag_obj.blender_obj
                tag_id = blender_obj.get("tag_id", 0)
                tag_fam = blender_obj.get("tag_family", tag_family)
                
                # Write to CSV
                detection = DetectionRecord(
                    image_id=image_name,
                    tag_id=tag_id,
                    tag_family=tag_fam,
                    corners=corners_2d,
                )
                csv_writer.write_detection(detection)
                
                # Write to COCO
                coco_writer.add_annotation(
                    image_id=coco_image_id,
                    category_id=category_id,
                    corners=corners_2d,
                    tag_id=tag_id,
                )
                
                total_detections += 1
    
    # Save COCO annotations
    coco_writer.save()
    
    print(f"✓ Generated {total_images} images with {total_detections} detections")
    print(f"  Output: {output_dir}")
    print(f"  CSV: {output_dir / 'tags.csv'}")
    print(f"  COCO: {output_dir / 'annotations.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

