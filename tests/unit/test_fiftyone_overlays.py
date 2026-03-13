import numpy as np

from render_tag.viz.fiftyone_tool import project_tag_axes


def test_project_tag_axes_logic():
    """Verify that project_tag_axes correctly projects 3D axes to 2D polylines."""
    # Mock record
    # Position at [0, 0, 1] relative to camera (Top-Left of tag)
    # Identity rotation (facing camera, though +Z points away in OpenCV,
    #                    our local +Z points to camera if rotated)
    # Actually, if rotation is identity, local axes match camera axes.
    # Cam: X right, Y down, Z forward.
    # Local: X right, Y down, Z forward.
    # tag_size_mm = 100.0, so axis_len_m = 0.05
    record = {
        "position": [0.0, 0.0, 1.0],
        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],  # Identity in WXYZ format
        "tag_size_mm": 100.0,
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

    # Calculate expected normalized 2D points
    # Origin (Top-Left): [0, 0, 1] -> [320/640, 240/480] = [0.5, 0.5]
    # X: [0.05, 0, 1] -> [ (0.05 * 500 / 1) + 320, 240 ] / res -> [345/640, 240/480]
    # Y: [0, 0.05, 1] -> [ 320, (0.05 * 500 / 1) + 240 ] / res -> [320/640, 265/480]
    # Z: [0, 0, 1.05] -> [ 320, 240 ] / res -> [320/640, 240/480]

    x_points = axes["axis_x"].points[0]
    np.testing.assert_allclose(x_points[0], [320 / 640, 240 / 480])
    np.testing.assert_allclose(x_points[1], [345 / 640, 240 / 480])

    y_points = axes["axis_y"].points[0]
    np.testing.assert_allclose(y_points[0], [320 / 640, 240 / 480])
    np.testing.assert_allclose(y_points[1], [320 / 640, 265 / 480])

    z_points = axes["axis_z"].points[0]
    np.testing.assert_allclose(z_points[0], [320 / 640, 240 / 480])
    np.testing.assert_allclose(z_points[1], [320 / 640, 240 / 480])
