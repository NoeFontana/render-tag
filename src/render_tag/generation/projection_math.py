"""
Pure-Python geometry math for tag projection and metadata calculation.
No Blender dependencies.
"""

from __future__ import annotations

import numpy as np


def calculate_distance(point1: np.ndarray, point2: np.ndarray) -> float:
    """Calculates Euclidean distance between two 3D points."""
    return float(np.linalg.norm(point1 - point2))


def calculate_angle_of_incidence(
    target_location: np.ndarray, target_normal: np.ndarray, camera_location: np.ndarray
) -> float:
    """
    Calculates the angle of incidence (in degrees) between a target surface and a camera.

    Args:
        target_location: 3D position of the target.
        target_normal: 3D normal vector of the target surface (world space).
        camera_location: 3D position of the camera.
    """
    # Normalize normal
    norm = np.linalg.norm(target_normal)
    if norm < 1e-10:
        return 0.0
    normal = target_normal / norm

    # Vector from target to camera
    to_cam = (camera_location - target_location).astype(np.float64)
    to_cam_norm = np.linalg.norm(to_cam)
    if to_cam_norm < 1e-10:
        return 0.0
    to_cam /= to_cam_norm

    # Cosine of angle is dot product
    cos_theta = np.clip(np.dot(normal, to_cam), -1.0, 1.0)
    angle_rad = np.arccos(cos_theta)
    return float(np.degrees(angle_rad))


def get_opencv_camera_matrix(blender_matrix: np.ndarray) -> np.ndarray:
    """
    Converts a 4x4 Blender Camera-to-World matrix to OpenCV convention.

    Blender: right=X, up=Y, forward=-Z
    OpenCV: right=X, down=Y, forward=Z
    """
    flip_mat = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
    return blender_matrix @ flip_mat


def get_world_normal(
    world_matrix: np.ndarray, local_normal: np.ndarray | None = None
) -> np.ndarray:
    """
    Transforms a local normal vector to world space using a 4x4 transformation matrix.
    """
    if local_normal is None:
        local_normal = np.array([0, 0, 1, 0])  # Default Z-up

    world_normal = (world_matrix @ local_normal)[:3]
    norm = np.linalg.norm(world_normal)
    if norm < 1e-10:
        return np.array([0.0, 0.0, 1.0])
    return world_normal / norm


def matrix_to_quaternion_wxyz(matrix: np.ndarray) -> list[float]:
    """Convert a 4x4 or 3x3 rotation matrix to a scalar-first unit quaternion [w, x, y, z].

    Uses a numerically stable algorithm (Shepperd's method) to avoid
    singularities.

    Args:
        matrix: 4x4 transformation matrix or 3x3 rotation matrix.

    Returns:
        List of 4 floats: [w, x, y, z].
    """
    m = np.asarray(matrix)[:3, :3]
    trace = np.trace(m)

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m[2, 1] - m[1, 2]) * s
        y = (m[0, 2] - m[2, 0]) * s
        z = (m[1, 0] - m[0, 1]) * s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s

    return [float(w), float(x), float(y), float(z)]


def matrix_to_quaternion_xyzw(matrix: np.ndarray) -> list[float]:
    """Convert a 4x4 or 3x3 rotation matrix to a scalar-last unit quaternion [x, y, z, w].

    Args:
        matrix: 4x4 transformation matrix or 3x3 rotation matrix.

    Returns:
        List of 4 floats: [x, y, z, w].
    """
    w, x, y, z = matrix_to_quaternion_wxyz(matrix)
    return [x, y, z, w]


def calculate_relative_pose(
    tag_world_matrix: np.ndarray, blender_cam_world_matrix: np.ndarray
) -> dict[str, list[float]]:
    """
    Calculates the relative pose of a tag in OpenCV camera coordinates.

    Args:
        tag_world_matrix: 4x4 matrix (World-to-Tag)
        blender_cam_world_matrix: 4x4 matrix (Blender Camera-to-World)

    Returns:
        Dict with 'position' ([x, y, z]) and 'rotation_quaternion' ([w, x, y, z])
    """
    # 1. Convert Blender Cam to OpenCV Cam
    # OpenCV: Z forward, Y down, X right
    opencv_cam_world = get_opencv_camera_matrix(blender_cam_world_matrix)

    # 2. Invert to get World-to-Camera (OpenCV)
    world_to_opencv_cam = np.linalg.inv(opencv_cam_world)

    # 3. Relative transformation: T_cam_tag = T_world_to_cam * T_tag_in_world
    rel_mat = world_to_opencv_cam @ tag_world_matrix

    # 4. Extract position and quaternion
    pos = rel_mat[:3, 3].tolist()
    quat = matrix_to_quaternion_wxyz(rel_mat)

    return {
        "position": [float(p) for p in pos],
        "rotation_quaternion": quat,
    }


def project_points(
    points_world: np.ndarray,
    cam_world_matrix: np.ndarray,
    resolution: list[int],
    fov: float,
) -> np.ndarray:
    """
    Projects 3D world points to 2D pixel coordinates using OpenCV convention.

    Args:
        points_world: (N, 3) array of 3D points in world space.
        cam_world_matrix: 4x4 Blender Camera-to-World matrix.
        resolution: [width, height] of the image.
        fov: Horizontal field of view in degrees.

    Returns:
        (N, 2) array of pixel coordinates [x, y].
        Points behind the camera (Z <= 0) are set to [-1e6, -1e6].
    """
    # 1. Transform points to OpenCV Camera space
    # OpenCV: Z forward, Y down, X right
    opencv_cam_world = get_opencv_camera_matrix(cam_world_matrix)
    world_to_cam = np.linalg.inv(opencv_cam_world)

    # Convert points to homogeneous coordinates (N, 4)
    points_h = np.hstack([points_world, np.ones((len(points_world), 1))])

    # Transform: points_cam = T_world_to_cam * points_world
    points_cam_h = (world_to_cam @ points_h.T).T
    points_cam = points_cam_h[:, :3]

    # 2. Projection
    width, height = resolution
    fov_rad = np.radians(fov)
    f = width / (2.0 * np.tan(fov_rad / 2.0))

    cx = width / 2.0
    cy = height / 2.0

    pixels = np.zeros((len(points_world), 2))
    z = points_cam[:, 2]
    mask = z > 1e-6  # Only project points in front of the camera

    pixels[mask, 0] = (points_cam[mask, 0] * f / z[mask]) + cx
    pixels[mask, 1] = (points_cam[mask, 1] * f / z[mask]) + cy

    # Mark points behind camera as far outside
    pixels[~mask] = -1e6

    return pixels


def calculate_pixel_area(pixels: np.ndarray) -> float:
    """
    Calculates the area of a polygon defined by 2D pixels using the Shoelace formula.

    Args:
        pixels: (N, 2) array of pixel coordinates.

    Returns:
        Area in pixels.
    """
    if len(pixels) < 3:
        return 0.0
    x = pixels[:, 0]
    y = pixels[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def calculate_ppm(
    distance_m: float,
    tag_size_m: float,
    focal_length_px: float,
    tag_grid_size: int
) -> float:
    """
    Calculates the visual resolution in Pixels Per Module (PPM).

    Formula: PPM = (f_px * tag_size_m) / (distance_m * tag_grid_size)

    Args:
        distance_m: Distance from camera to tag in meters.
        tag_size_m: Physical size of the tag in meters.
        focal_length_px: Effective focal length of the camera in pixels.
        tag_grid_size: Number of modules (bits) across the tag.
    """
    if distance_m < 1e-6 or tag_grid_size == 0:
        return 0.0
    return (focal_length_px * tag_size_m) / (distance_m * tag_grid_size)


def solve_distance_for_ppm(
    target_ppm: float,
    tag_size_m: float,
    focal_length_px: float,
    tag_grid_size: int
) -> float:
    """
    Calculates the required distance to achieve a target PPM.

    Formula: distance_m = (f_px * tag_size_m) / (target_ppm * tag_grid_size)

    Args:
        target_ppm: Desired visual resolution in Pixels Per Module.
        tag_size_m: Physical size of the tag in meters.
        focal_length_px: Effective focal length of the camera in pixels.
        tag_grid_size: Number of modules (bits) across the tag.
    """
    if target_ppm < 1e-6 or tag_grid_size == 0:
        return 100.0  # Safe default far distance
    return (focal_length_px * tag_size_m) / (target_ppm * tag_grid_size)


def calculate_incidence_angle(cam_world_matrix: np.ndarray, tag_world_matrix: np.ndarray) -> float:
    """
    Calculates the angle of incidence between the camera forward vector and the tag normal.

    Args:
        cam_world_matrix: 4x4 Blender Camera-to-World matrix.
        tag_world_matrix: 4x4 Tag World matrix.

    Returns:
        Angle in degrees (0 = facing, 90 = side-on).
    """
    # 1. Tag Normal in World Space (Z-up)
    tag_normal_world = tag_world_matrix[:3, 2]
    tag_normal_world /= np.linalg.norm(tag_normal_world)

    # 2. Camera Location
    cam_loc = cam_world_matrix[:3, 3]
    # 3. Tag Location
    tag_loc = tag_world_matrix[:3, 3]

    # 4. Vector from Tag to Camera
    v_tag_cam = cam_loc - tag_loc
    v_tag_cam_norm = np.linalg.norm(v_tag_cam)
    if v_tag_cam_norm < 1e-6:
        return 0.0
    v_tag_cam /= v_tag_cam_norm

    # 5. Angle is arccos of dot product
    cos_theta = np.clip(np.dot(tag_normal_world, v_tag_cam), -1.0, 1.0)
    angle_rad = np.arccos(cos_theta)
    return float(np.degrees(angle_rad))


def euler_to_matrix(euler: list[float]) -> np.ndarray:
    """
    Converts XYZ Euler angles (radians) to a 3x3 rotation matrix.
    Uses Blender's default XYZ order.
    """
    ex, ey, ez = euler
    cx, sx = np.cos(ex), np.sin(ex)
    cy, sy = np.cos(ey), np.sin(ey)
    cz, sz = np.cos(ez), np.sin(ez)

    # Rx * Ry * Rz
    # Rx
    mat_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    # Ry
    mat_y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    # Rz
    mat_z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])

    # Blender uses XYZ order which means Rotate X then Y then Z
    # In matrix math this is Rz * Ry * Rx @ point
    return mat_z @ mat_y @ mat_x


def get_world_matrix(
    location: list[float], rotation_euler: list[float], scale: list[float] | None = None
) -> np.ndarray:
    """
    Creates a 4x4 transformation matrix from location, euler rotation, and scale.
    """
    if scale is None:
        scale = [1, 1, 1]

    res = np.eye(4)
    # Rotation
    res[:3, :3] = euler_to_matrix(rotation_euler)
    # Scale
    res[:3, :3] = res[:3, :3] * np.array(scale)
    # Translation
    res[:3, 3] = location
    return res
