from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import generate_subject_records


@patch("render_tag.backend.projection.bridge")
def test_generate_subject_records_tag(mock_bridge):
    # Setup mocks
    mock_obj = MagicMock()
    mock_obj.blender_obj = {
        "type": "TAG",
        "tag_id": 42,
        "tag_family": "tag36h11",
        "keypoints_3d": [
            [-0.05, 0.05, 0.0],
            [0.05, 0.05, 0.0],
            [0.05, -0.05, 0.0],
            [-0.05, -0.05, 0.0],
        ],
    }

    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 1]

    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 0]
    mock_bridge.bpy.context.scene.render.resolution_x = 640
    mock_bridge.bpy.context.scene.render.resolution_y = 480

    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.array(
        [[500, 0, 320], [0, 500, 240], [0, 0, 1]]
    )

    # We need to mock project_points because it uses internal logic
    # that might be complex to mock fully
    with patch("render_tag.backend.projection.project_points") as mock_proj:
        mock_proj.return_value = np.array([[300, 200], [340, 200], [340, 280], [300, 280]])

        records = generate_subject_records(mock_obj, "test_img")

        assert len(records) == 1
        record = records[0]
        assert record.tag_id == 42
        assert record.record_type == "TAG"
        assert len(record.corners) == 4


@patch("render_tag.backend.projection.bridge")
def test_generate_subject_records_board(mock_bridge):
    mock_obj = MagicMock()
    # 3x3 board corners + 4 saddle points = 13 keypoints
    kps = [[0, 0, 0]] * 13
    mock_obj.blender_obj = {
        "type": "BOARD",
        "tag_id": 0,
        "tag_family": "calibration_board",
        "keypoints_3d": kps,
    }

    mock_obj.get_local2world_mat.return_value = np.eye(4)
    mock_obj.get_location.return_value = [0, 0, 2]

    mock_bridge.np = np
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = [0, 0, 0]
    mock_bridge.bpy.context.scene.render.resolution_x = 1920
    mock_bridge.bpy.context.scene.render.resolution_y = 1080

    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = np.eye(3)

    with patch("render_tag.backend.projection.project_points") as mock_proj:
        mock_proj.return_value = np.array(
            [[100, 100], [200, 100], [200, 200], [100, 200]] + [[100, 100]] * 9
        )
        
        records = generate_subject_records(mock_obj, "test_img")

        assert len(records) == 1
        record = records[0]
        assert record.tag_family == "calibration_board"
        assert record.record_type == "SUBJECT"
        assert len(record.corners) == 4
        assert len(record.keypoints) == 9  # 13 - 4
