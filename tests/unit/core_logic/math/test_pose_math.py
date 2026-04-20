import numpy as np

from render_tag.core.geometry.projection_math import matrix_to_quaternion_xyzw


def test_matrix_to_quaternion_identity():
    """Verify that identity matrix converts to identity quaternion [0, 0, 0, 1]."""
    matrix = np.eye(4)
    q = matrix_to_quaternion_xyzw(matrix)
    assert np.allclose(q, [0.0, 0.0, 0.0, 1.0])


def test_matrix_to_quaternion_90_x():
    """Verify rotation around X axis."""
    # 90 degrees around X
    c = 0.0
    s = 1.0
    matrix = np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])
    q = matrix_to_quaternion_xyzw(matrix)
    # expected q = [sin(45), 0, 0, cos(45)] = [0.707, 0, 0, 0.707]
    expected = [np.sqrt(2) / 2, 0, 0, np.sqrt(2) / 2]
    assert np.allclose(q, expected)


def test_matrix_to_quaternion_translation_ignored():
    """Verify that translation part doesn't affect rotation quaternion."""
    matrix = np.eye(4)
    matrix[:3, 3] = [10, 20, 30]
    q = matrix_to_quaternion_xyzw(matrix)
    assert np.allclose(q, [0.0, 0.0, 0.0, 1.0])


def test_calculate_relative_pose_identity():
    """Verify relative pose when tag and camera are aligned (identity)."""
    from render_tag.core.geometry.projection_math import calculate_relative_pose

    # Tag at world origin
    tag_mat = np.eye(4)

    # Camera at origin with identity blender matrix
    blender_cam_mat = np.eye(4)

    pose = calculate_relative_pose(tag_mat, blender_cam_mat)

    # Position should be 0
    assert np.allclose(pose["position"], [0.0, 0.0, 0.0])

    # With the new OpenCV 4.6.0 convention, we apply an X-flip for the camera frame
    # and another X-flip for the object frame. For an identity tag and identity camera,
    # these flips cancel out, resulting in an identity rotation in OpenCV space.
    # wxyz: [1.0, 0.0, 0.0, 0.0]
    assert np.allclose(pose["rotation_quaternion"], [1.0, 0.0, 0.0, 0.0])


def test_calculate_relative_pose_translation():
    """Verify relative pose with translation."""
    from render_tag.core.geometry.projection_math import calculate_relative_pose

    # Tag at [0, 0, 5] in world
    tag_mat = np.eye(4)
    tag_mat[:3, 3] = [0, 0, 5]

    # Camera at [0, 0, 0] in world, identity blender matrix (looking at -Z)
    blender_cam_mat = np.eye(4)

    pose = calculate_relative_pose(tag_mat, blender_cam_mat)

    # In OpenCV cam space:
    # World Z axis is OpenCV -Z axis (because of flip)
    # So tag at world [0, 0, 5] is at OpenCV [0, 0, -5]
    assert np.allclose(pose["position"], [0.0, 0.0, -5.0])
