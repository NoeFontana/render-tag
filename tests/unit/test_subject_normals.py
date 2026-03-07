from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import check_tag_facing_camera


@patch("render_tag.backend.projection.bridge")
@patch("render_tag.backend.projection.is_facing_camera")
def test_check_tag_facing_camera_respects_custom_normal(mock_is_facing, mock_bridge):
    """
    Test that check_tag_facing_camera correctly uses a custom forward_axis
    if provided in blender_obj.
    """
    mock_bridge.np = np

    # Camera at (0, 10, 0), looking at origin (facing +Y direction)
    mock_bridge.bpy.context.scene.camera.location = np.array([0, 10, 0])

    mock_tag = MagicMock()
    mock_tag.get_local2world_mat.return_value = np.eye(4)
    mock_tag.get_location.return_value = np.array([0, 0, 0])

    # CASE 1: Default (Z-up)
    # Tag normal is [0,0,1]. Vector to camera is [0,10,0]. Dot product = 0.
    # Should return False or whatever is_facing_camera returns for 90 deg.
    mock_tag.blender_obj = {"type": "SUBJECT"}
    check_tag_facing_camera(mock_tag)

    # Inspect what normal was passed to is_facing_camera
    args, _ = mock_is_facing.call_args
    passed_normal = args[1]
    assert np.allclose(passed_normal, [0, 0, 1])

    # CASE 2: Custom forward axis [+Y]
    # Tag normal is [0,1,0]. Vector to camera is [0,10,0]. Dot product = 10 (facing).
    # THIS SHOULD WORK after the fix.
    # Currently it will likely pass [0,0,1] again.
    mock_tag.blender_obj = {"type": "SUBJECT", "forward_axis": [0, 1, 0, 0]}
    check_tag_facing_camera(mock_tag)

    args, _ = mock_is_facing.call_args
    passed_normal = args[1]

    # THIS ASSERTION SHOULD FAIL with current code
    assert np.allclose(passed_normal, [0, 1, 0]), f"Expected normal [0,1,0], got {passed_normal}"
