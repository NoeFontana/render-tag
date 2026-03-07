from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import generate_subject_records


@patch("render_tag.backend.projection.bridge")
def test_generate_subject_records_tag_scale(mock_bridge):
    """
    Verify if generate_subject_records correctly handles scaled world matrices for TAGs.
    If SVD is present, it will strip scale, which is WRONG for normalized keypoints.
    """
    mock_obj = MagicMock()
    # Normalized keypoints [-1, 1]
    kps = [[-1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, -1.0, 0.0], [-1.0, -1.0, 0.0]]
    mock_obj.blender_obj = {
        "type": "TAG",
        "tag_id": 1,
        "tag_family": "tag36h11",
        "keypoints_3d": kps,
    }

    # World matrix with scale 0.05 (for a 0.1m tag, since plane is 2x2)
    world_matrix = np.eye(4) * 0.05
    world_matrix[3, 3] = 1.0  # Restore homogeneous w
    world_matrix[0:3, 3] = [0, 0, 1]  # Translation to z=1

    mock_obj.get_local2world_mat.return_value = world_matrix
    mock_obj.get_location.return_value = [0, 0, 1]

    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 0]
    mock_bridge.bpy.context.scene.render.resolution_x = 640
    mock_bridge.bpy.context.scene.render.resolution_y = 480

    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.array(
        [[500, 0, 320], [0, 500, 240], [0, 0, 1]]
    )

    with patch("render_tag.backend.projection.project_points") as mock_proj:
        # Mock projection to return valid CW corners: TL, TR, BR, BL
        mock_proj.return_value = np.array([[100, 100], [200, 100], [200, 200], [100, 200]])

        generate_subject_records(mock_obj, "test_img")

        args, _ = mock_proj.call_args
        world_kps_used = args[0]

        expected_tl = np.array([-0.05, 0.05, 1.0])
        actual_tl = world_kps_used[0]

        # This will fail if scale was stripped
        np.testing.assert_array_almost_equal(
            actual_tl, expected_tl, err_msg="Scale was stripped from TAG projection!"
        )
