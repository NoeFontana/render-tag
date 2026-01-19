#!/usr/bin/env python3
"""
Visual debugging tool for render-tag output verification.

This script reads generated images and CSV annotations, then draws
the detected corners to visually verify alignment.

Usage:
    render-tag viz --output output/dataset_01
    render-tag viz --output output/dataset_01 --image scene_0001_cam_0001
"""

import argparse
import csv
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw


def load_detections(csv_path: Path) -> dict[str, list[dict]]:
    """Load detections from CSV file.
    
    Returns:
        Dictionary mapping image_id to list of detections
    """
    detections: dict[str, list[dict]] = {}
    
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_id = row["image_id"]
            corners = [
                (float(row["x1"]), float(row["y1"])),
                (float(row["x2"]), float(row["y2"])),
                (float(row["x3"]), float(row["y3"])),
                (float(row["x4"]), float(row["y4"])),
            ]
            detection = {
                "tag_id": int(row["tag_id"]),
                "tag_family": row.get("tag_family", "unknown"),
                "corners": corners,
            }
            
            if image_id not in detections:
                detections[image_id] = []
            detections[image_id].append(detection)
    
    return detections


def draw_detection(
    draw: ImageDraw.ImageDraw,
    corners: list[tuple[float, float]],
    tag_id: int,
    color: str = "lime",
    line_width: int = 2,
) -> None:
    """Draw a detection on the image.
    
    Args:
        draw: PIL ImageDraw object
        corners: List of 4 (x, y) corner coordinates
        tag_id: Tag ID to display
        color: Line color
        line_width: Line width in pixels
    """
    if len(corners) != 4:
        return
    
    # Draw quadrilateral
    for i in range(4):
        start = corners[i]
        end = corners[(i + 1) % 4]
        draw.line([start, end], fill=color, width=line_width)
    
    # Draw corner markers
    marker_size = 5
    corner_colors = ["red", "orange", "yellow", "green"]  # BL, BR, TR, TL
    for i, corner in enumerate(corners):
        x, y = corner
        draw.ellipse(
            [x - marker_size, y - marker_size, x + marker_size, y + marker_size],
            fill=corner_colors[i],
            outline="white",
        )
    
    # Draw tag ID label
    centroid_x = sum(c[0] for c in corners) / 4
    centroid_y = sum(c[1] for c in corners) / 4
    draw.text((centroid_x, centroid_y), f"ID:{tag_id}", fill="white")


def visualize_image(
    image_path: Path,
    detections: list[dict],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> Image.Image:
    """Visualize detections on an image.
    
    Args:
        image_path: Path to the image file
        detections: List of detection dictionaries
        output_path: Optional path to save the visualization
        show: Whether to display the image
        
    Returns:
        The annotated image
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    colors = ["lime", "cyan", "magenta", "yellow", "red"]
    
    for i, detection in enumerate(detections):
        color = colors[i % len(colors)]
        draw_detection(
            draw,
            detection["corners"],
            detection["tag_id"],
            color=color,
        )
    
    if output_path:
        img.save(output_path)
        print(f"Saved visualization to: {output_path}")
    
    if show:
        img.show()
    
    return img


def visualize_dataset(
    output_dir: Path,
    specific_image: Optional[str] = None,
    save_viz: bool = True,
) -> None:
    """Visualize all or specific images in a dataset.
    
    Args:
        output_dir: Path to the dataset output directory
        specific_image: Optional specific image ID to visualize
        save_viz: Whether to save visualizations
    """
    csv_path = output_dir / "tags.csv"
    images_dir = output_dir / "images"
    viz_dir = output_dir / "visualizations"
    
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        print("Run 'render-tag generate' first to create data.")
        return
    
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}")
        return
    
    # Load all detections
    detections = load_detections(csv_path)
    print(f"Loaded {sum(len(d) for d in detections.values())} detections from {len(detections)} images")
    
    if save_viz:
        viz_dir.mkdir(parents=True, exist_ok=True)
    
    # Process images
    if specific_image:
        image_ids = [specific_image] if specific_image in detections else []
        if not image_ids:
            print(f"Warning: No detections found for image: {specific_image}")
            # Still try to show the image
            image_path = images_dir / f"{specific_image}.png"
            if image_path.exists():
                img = Image.open(image_path)
                img.show()
            return
    else:
        image_ids = list(detections.keys())
    
    for image_id in image_ids:
        image_path = images_dir / f"{image_id}.png"
        if not image_path.exists():
            print(f"Warning: Image not found: {image_path}")
            continue
        
        output_path = viz_dir / f"{image_id}_viz.png" if save_viz else None
        
        print(f"Visualizing: {image_id} ({len(detections.get(image_id, []))} detections)")
        visualize_image(
            image_path,
            detections.get(image_id, []),
            output_path=output_path,
            show=(specific_image is not None),  # Only show if specific image requested
        )


def main() -> None:
    """Entry point for the viz tool."""
    parser = argparse.ArgumentParser(
        description="Visualize render-tag detections for debugging"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Path to the dataset output directory",
    )
    parser.add_argument(
        "--image", "-i",
        type=str,
        default=None,
        help="Specific image ID to visualize (without extension)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save visualization images",
    )
    
    args = parser.parse_args()
    
    visualize_dataset(
        args.output,
        specific_image=args.image,
        save_viz=not args.no_save,
    )


if __name__ == "__main__":
    main()
