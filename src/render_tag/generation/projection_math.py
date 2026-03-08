"""
Pure-Python geometry math for tag projection and metadata calculation.
No Blender dependencies.
"""

from __future__ import annotations

import numpy as np

from render_tag.generation.math import Matrix3x3, Matrix4x4, Vector3


def calculate_distance(point1: Vector3, point2: Vector3) -> float:
    """Calculates Euclidean distance between two 3D points."""
    return float(np.linalg.norm(point1 - point2))


def calculate_angle_of_incidence(
    target_location: Vector3, target_normal: Vector3, camera_location: Vector3
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


def get_opencv_camera_matrix(blender_matrix: Matrix4x4) -> Matrix4x4:
    """
    Converts a 4x4 Blender Camera-to-World matrix to OpenCV convention.

    Blender: right=X, up=Y, forward=-Z
    OpenCV: right=X, down=Y, forward=Z

    This implementation uses a column-swizzle to ensure the determinant
    remains positive (+1) for rigid transformations.
    """
    # Blender Columns: [X, Y, Z, T]
    # OpenCV Columns:  [X, -Y, -Z, T]
    opencv_matrix = np.copy(blender_matrix)
    opencv_matrix[:, 1] = -blender_matrix[:, 1]
    opencv_matrix[:, 2] = -blender_matrix[:, 2]
    return opencv_matrix


def get_world_normal(world_matrix: Matrix4x4, local_normal: Vector3 | None = None) -> Vector3:
    """
    Transforms a local normal vector to world space using the inverse-transpose contract.

    Surface normals are covariant vectors; to correctly map them across non-uniform
    affine transformations (scaling/shear), we must multiply by the transpose of
    the inverse of the upper-left 3x3 block.
    """
    if local_normal is None:
        local_normal = np.array([0.0, 0.0, 1.0])  # Default Z-up

    # Ensure local_normal is a 3D unit vector
    local_normal = np.asarray(local_normal)[:3].astype(np.float64)
    norm_local = np.linalg.norm(local_normal)
    if norm_local > 1e-10:
        local_normal /= norm_local

    # 1. Isolate the deformation block (rotation + scale)
    m_rs = world_matrix[:3, :3]

    # 2. Apply inverse-transpose contract
    # If matrix is singular or near-singular, fallback to identity/original
    try:
        m_normal_transform = np.linalg.inv(m_rs).T
        world_normal = m_normal_transform @ local_normal
    except np.linalg.LinAlgError:
        # Fallback for degenerate matrices: use the raw transform and hope for the best
        world_normal = m_rs @ local_normal

    # 3. Re-normalize world-space normal
    norm_world = np.linalg.norm(world_normal)
    if norm_world < 1e-10:
        return np.array([0.0, 0.0, 1.0])
    return world_normal / norm_world


def sanitize_to_rigid_transform(matrix: Matrix4x4) -> Matrix4x4:
    """
    Exctracts a pure SE(3) rigid-body transformation from a scaled affine matrix.

    This function acts as a mandatory geometric sanitization boundary, stripping
    graphics-layer scale factors to enforce perception-layer metric invariants.
    """
    m = np.asarray(matrix)
    res = np.eye(4)

    # 1. Translation Extraction (unaffected by local scaling)
    res[:3, 3] = m[:3, 3]

    # 2. Rotation Orthogonalization
    # Extract the 3x3 block and normalize each column vector by its Euclidean norm.
    # This restores the matrix to the SO(3) pure rotation group.
    rot_block = m[:3, :3].copy()
    norms = np.linalg.norm(rot_block, axis=0)

    # Avoid division by zero for degenerate axes
    mask = norms > 1e-10
    rot_block[:, mask] /= norms[mask]
    rot_block[:, ~mask] = np.eye(3)[:, ~mask]

    res[:3, :3] = rot_block
    return res


def matrix_to_quaternion_wxyz(matrix: Matrix4x4 | Matrix3x3) -> list[float]:
    """Convert a 4x4 or 3x3 rotation matrix to a scalar-first unit quaternion [w, x, y, z].

    Uses a numerically stable algorithm (Shepperd's method) to avoid
    singularities.

    Args:
        matrix: 4x4 transformation matrix or 3x3 rotation matrix.

    Returns:
        List of 4 floats: [w, x, y, z].
    """
    m = np.asarray(matrix)[:3, :3]

    # Enforce pure rotation invariants SO(3) to prevent quaternion corruption
    assert np.allclose(m.T @ m, np.eye(3), atol=1e-4), (
        "Matrix is not orthogonal (contains scale or shear)"
    )
    assert np.isclose(np.linalg.det(m), 1.0, atol=1e-4), (
        "Matrix determinant is not +1 (contains reflection or scale)"
    )

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


def matrix_to_quaternion_xyzw(matrix: Matrix4x4 | Matrix3x3) -> list[float]:
    """Convert a 4x4 or 3x3 rotation matrix to a scalar-last unit quaternion [x, y, z, w].

    Args:
        matrix: 4x4 transformation matrix or 3x3 rotation matrix.

    Returns:
        List of 4 floats: [x, y, z, w].
    """
    w, x, y, z = matrix_to_quaternion_wxyz(matrix)
    return [x, y, z, w]


def quaternion_xyzw_to_matrix(quat: list[float]) -> Matrix3x3:
    """Convert a scalar-last unit quaternion [x, y, z, w] to a 3x3 rotation matrix."""
    x, y, z, w = quat
    return np.array(
        [
            [1 - 2 * y**2 - 2 * z**2, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w],
            [2 * x * y + 2 * z * w, 1 - 2 * x**2 - 2 * z**2, 2 * y * z - 2 * x * w],
            [2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x**2 - 2 * y**2],
        ]
    )


def quaternion_wxyz_to_matrix(quat: list[float]) -> Matrix3x3:
    """Convert a scalar-first unit quaternion [w, x, y, z] to a 3x3 rotation matrix."""
    w, x, y, z = quat
    return quaternion_xyzw_to_matrix([x, y, z, w])


def calculate_relative_pose(
    tag_world_matrix: Matrix4x4, blender_cam_world_matrix: Matrix4x4
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

    # 4. Extract position and orthogonalize rotation via sanitization boundary
    sanitized_rel_mat = sanitize_to_rigid_transform(rel_mat)

    pos = sanitized_rel_mat[:3, 3].tolist()
    orthogonal_rot = sanitized_rel_mat[:3, :3]

    quat = matrix_to_quaternion_wxyz(orthogonal_rot)

    return {
        "position": [float(p) for p in pos],
        "rotation_quaternion": quat,
    }


def project_points(
    points_world: np.ndarray,
    cam_world_matrix: Matrix4x4,
    resolution: list[int],
    k_matrix: list[list[float]],
) -> np.ndarray:
    """
    Projects 3D world points to 2D pixel coordinates using OpenCV convention.

    Args:
        points_world: (N, 3) array of 3D points in world space.
        cam_world_matrix: 4x4 Blender Camera-to-World matrix (OpenCV convention).
        resolution: [width, height] of the image.
        k_matrix: 3x3 intrinsic matrix [[fx, 0, cx], [0, fy, cy], [0, 0, 1]].

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

    # 2. Projection using K matrix
    fx = k_matrix[0][0]
    fy = k_matrix[1][1]
    cx = k_matrix[0][2]
    cy = k_matrix[1][2]

    pixels = np.zeros((len(points_world), 2))
    z = points_cam[:, 2]
    mask = z > 1e-6  # Only project points in front of the camera

    pixels[mask, 0] = (points_cam[mask, 0] * fx / z[mask]) + cx
    pixels[mask, 1] = (points_cam[mask, 1] * fy / z[mask]) + cy

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
    z_depth_m: float, tag_size_m: float, focal_length_px: float, tag_grid_size: int
) -> float:
    """
    Calculates the visual resolution in Pixels Per Module (PPM).

    Formula: PPM = (f_px * tag_size_m) / (z_depth_m * tag_grid_size)

    Args:
        z_depth_m: Orthogonal distance (Z-depth) from camera to tag in meters.
        tag_size_m: Physical size of the tag in meters.
        focal_length_px: Effective focal length of the camera in pixels.
        tag_grid_size: Number of modules (bits) across the tag.
    """
    if z_depth_m < 1e-6 or tag_grid_size == 0:
        return 0.0
    return (focal_length_px * tag_size_m) / (z_depth_m * tag_grid_size)


def solve_distance_for_ppm(
    target_ppm: float, tag_size_m: float, focal_length_px: float, tag_grid_size: int
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


def calculate_incidence_angle(cam_world_matrix: Matrix4x4, tag_world_matrix: Matrix4x4) -> float:
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


def validate_winding_order(corners: list[tuple[float, float]]) -> bool:
    """
    Validates that a polygon is purely Clockwise in a Y-down coordinate system.
    Uses the signed area (Shoelace formula).

    In Y-down:
    - Positive area = Clockwise
    - Negative area = Counter-Clockwise
    - Zero area = Degenerate or self-intersecting (bowtie)

    Args:
        corners: List of (x, y) tuples.

    Returns:
        True if Clockwise and non-degenerate.
    """
    if len(corners) < 3:
        return False

    pts = np.array(corners)
    x = pts[:, 0]
    y = pts[:, 1]

    # Shoelace formula for signed area
    # Area = 0.5 * sum(x_i * y_{i+1} - x_{i+1} * y_i)
    signed_area = 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    # In Y-down, CW is positive.
    # We also want to ensure it's not a bowtie.
    # For 4 points, if it's convex and CW, area is significantly positive.
    # If it's a bowtie, the signed area will be small (difference of two triangles).
    return bool(signed_area > 1e-6)


def euler_to_matrix(euler: list[float]) -> Matrix3x3:
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
) -> Matrix4x4:
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
