"""
Tag generation utilities using OpenCV.

This module provides functions to generate AprilTag and ArUco marker images
on the fly using cv2.aruco.
"""

from pathlib import Path

import cv2
import numpy as np

# Map TagFamily enum values/strings to OpenCV ArUco constants
TAG_DICT_MAP = {
    # AprilTag families (OpenCV 4.x+)
    "tag16h5": cv2.aruco.DICT_APRILTAG_16h5,
    "tag25h9": cv2.aruco.DICT_APRILTAG_25h9,
    "tag36h10": cv2.aruco.DICT_APRILTAG_36h10,
    "tag36h11": cv2.aruco.DICT_APRILTAG_36h11,
    # ArUco dictionaries
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
    "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
    "DICT_7X7_100": cv2.aruco.DICT_7X7_100,
    "DICT_7X7_250": cv2.aruco.DICT_7X7_250,
    "DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
    "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
}


def generate_tag_image(
    family: str,
    tag_id: int,
    size_pixels: int = 512,
    border_bits: int = 1,
) -> np.ndarray | None:
    """Generate a marker image for a given family and ID.

    Args:
        family: Tag family name (e.g., "tag36h11" or "DICT_4X4_50")
        tag_id: The marker ID to generate
        size_pixels: Size of the output image in pixels (square)
        border_bits: Thickness of the black border in bits

    Returns:
        Numpy array (grayscale image) or None if family not supported
    """
    if family not in TAG_DICT_MAP:
        return None

    dictionary = cv2.aruco.getPredefinedDictionary(TAG_DICT_MAP[family])

    # Generate the marker
    marker_img = cv2.aruco.generateImageMarker(
        dictionary, tag_id, size_pixels, borderBits=border_bits
    )

    return marker_img


def ensure_tag_asset(
    family: str,
    tag_id: int,
    output_dir: Path,
    size_pixels: int = 512,
) -> Path:
    """Ensure a tag asset exists on disk, generating it if necessary.

    Args:
        family: Tag family name
        tag_id: Marker ID
        output_dir: Directory where assets are stored
        size_pixels: Pixel size for generated image

    Returns:
        Path to the asset file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{family}_{tag_id}.png"
    asset_path = output_dir / filename

    if not asset_path.exists():
        img = generate_tag_image(family, tag_id, size_pixels=size_pixels)
        if img is not None:
            cv2.imwrite(str(asset_path), img)

    return asset_path
