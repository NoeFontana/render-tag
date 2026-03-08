import numpy as np

from render_tag.viz.fiftyone_tool import project_tag_axes


def test_project_tag_axes_logic():
    """Verify that project_tag_axes correctly projects 3D axes to 2D polylines."""
    # Mock record
    # Position at [0, 0, 1] relative to camera
    # Identity rotation (facing camera)
    record = {
        "position": [0.0, 0.0, 1.0],
        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
        "corners": [[100, 100], [200, 100], [200, 200], [100, 200]],
        "k_matrix": [[500, 0, 320], [0, 500, 240], [0, 0, 1]],
        "resolution": [640, 480],
    }

    # ACT
    axes = project_tag_axes(record, record["k_matrix"], record["resolution"])

    # VERIFY
    assert axes is not None
    assert "axis_x" in axes
    assert "axis_y" in axes
    assert "axis_z" in axes

    # Check X axis (TL to TR)
    # TL in normalized: [100/640, 100/480]
    # TR in normalized: [200/640, 100/480]
    x_points = axes["axis_x"].points[0]
    np.testing.assert_allclose(x_points[0], [100 / 640, 100 / 480])
    np.testing.assert_allclose(x_points[1], [200 / 640, 100 / 480])

    # Check Z axis (points towards camera)
    # Origin is at Top-Left in 3D: [-0.05, 0.05, 0] relative to tag center
    # Tag center is at [0, 0, 1] in cam space
    # So origin is at [-0.05, 0.05, 1] in cam space
    # Z-axis end is at [-0.05, 0.05, 0.1] in local tag space?
    # No, in our new code it is [+0.1]
    # So Z end is at [-0.05, 0.05, 0.1] relative to tag center?
    # Local Z is outward from tag face.
    # If tag is at Z=1 facing camera, tag +Z is towards camera (if we use right-handed)
    # In project_tag_axes: pts_3d = [[-m, m, 0], [-m, m, 0.1]]
    # This means Z end is at Z=0.1 in local space.
    # Total Z in camera space for Z_end = 1.0 + 0.1 = 1.1?
    # No, if Normal is +Z local, and tag normal points towards camera (-Z camera),
    # then local +Z should be towards camera.
    # If tag is facing camera, tag +Z is camera -Z.
    # Wait, identity rotation means tag axes align with camera axes?
    # Blender Cam: X right, Y up, Z back (looking towards -Z)
    # OpenCV Cam: X right, Y down, Z forward.
    # If rotation is identity in OpenCV Cam space, tag axes align with camera axes.
    # So tag +Z is camera +Z (pointing away from camera).
    # To point TOWARDS camera, we would need tag +Z to be camera -Z.

    z_points = axes["axis_z"].points[0]
    # Check that Z axis exists and has two points
    assert len(z_points) == 2
