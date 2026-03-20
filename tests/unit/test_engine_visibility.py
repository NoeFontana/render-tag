from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.engine import _extract_and_save_ground_truth
from render_tag.core.schema import CameraIntrinsics, CameraRecipe


@patch("render_tag.backend.engine.generate_subject_records")
def test_extract_and_save_ground_truth_skip_visibility_no_full_screen(mock_subject_records):
    """
    Test that _extract_and_save_ground_truth does NOT return full-screen dummy corners
    when skip_visibility=True for TAGs.
    """
    ctx = MagicMock()
    ctx.skip_visibility = True
    ctx.coco_writer.add_image.return_value = 1

    tag_obj = MagicMock()
    tag_obj.blender_obj = {"type": "TAG", "tag_id": 42, "tag_family": "tag36h11"}

    tag_objects = [tag_obj]
    image_name = "test_img"
    res = [640, 480]
    scene_logger = MagicMock()

    # Expected real record
    mock_subject_records.return_value = [
        MagicMock(corners=[(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)])
    ]

    # Minimal camera recipe
    cam_recipe = CameraRecipe(
        transform_matrix=np.eye(4).tolist(),
        intrinsics=CameraIntrinsics(resolution=res, k_matrix=np.eye(3).tolist()),
    )

    _extract_and_save_ground_truth(tag_objects, image_name, 1, res, ctx, scene_logger, cam_recipe)

    # Check if generate_subject_records was called
    mock_subject_records.assert_called()

    # Check if it didn't use the hardcoded corners
    # We can check what was passed to coco_writer.add_detection
    # Actually, _extract_and_save_ground_truth calls generate_subject_records or uses dummy corners.
    # We want it to use generate_subject_records.
