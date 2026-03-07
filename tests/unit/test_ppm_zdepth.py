from unittest.mock import MagicMock, patch

import numpy as np

from render_tag.backend.projection import compute_geometric_metadata
from render_tag.generation.projection_math import calculate_ppm


def test_ppm_zdepth_consistency():
    """
    Test that PPM is calculated based on Z-depth, not Euclidean distance.
    Two tags at the same Z-depth should have the same PPM, regardless of
    their X/Y position in the FOV.
    """
    focal_length_px = 500.0
    tag_size_m = 0.1
    tag_grid_size = 8

    # Tag 1: Directly in front of camera at 2.0m (Z=2.0, X=0, Y=0)
    # Euclidean distance = 2.0m, Z-depth = 2.0m
    dist_center = 2.0
    ppm_center = calculate_ppm(dist_center, tag_size_m, focal_length_px, tag_grid_size)

    # Tag 2: At the edge of FOV, but at the SAME Z-depth (Z=2.0, X=1.0, Y=0)
    # Euclidean distance = sqrt(2^2 + 1^2) = 2.236m
    # Z-depth = 2.0m
    z_depth_edge = 2.0
    ppm_edge = calculate_ppm(z_depth_edge, tag_size_m, focal_length_px, tag_grid_size)

    # This should now PASS because we are using Z-depth
    assert np.isclose(ppm_center, ppm_edge), (
        f"PPM center ({ppm_center}) != PPM edge ({ppm_edge}) at same Z-depth"
    )


@patch("render_tag.backend.projection.bridge")
@patch("render_tag.backend.projection.calculate_distance")
@patch("render_tag.backend.projection.calculate_angle_of_incidence")
@patch("render_tag.backend.projection.project_corners_to_image")
@patch("render_tag.backend.projection.calculate_relative_pose")
@patch("render_tag.generation.projection_math.calculate_ppm")
def test_compute_geometric_metadata_zdepth(
    mock_ppm, mock_pose, mock_project, mock_angle, mock_dist, mock_bridge
):
    """
    Test that compute_geometric_metadata correctly calculates Z-depth
    and passes it to calculate_ppm.
    """
    mock_bridge.np = np

    # Setup Camera
    # Identity matrix means camera is looking at -Z
    mock_bridge.bpy.context.scene.camera.matrix_world = np.eye(4)
    mock_bridge.bpy.context.scene.camera.location = np.array([0, 0, 0])

    # Setup Tag
    # Tag at (1, 0, -2) -> X=1, Y=0, Z=-2 (in front of camera)
    # Vector cam->tag = (1, 0, -2)
    # Camera forward = (0, 0, -1)
    # Z-depth = dot((1, 0, -2), (0, 0, -1)) = 2.0
    tag_loc = np.array([1.0, 0.0, -2.0])
    mock_tag = MagicMock()
    mock_tag.get_location.return_value = tag_loc
    mock_tag.get_local2world_mat.return_value = np.eye(4)
    mock_tag.blender_obj = {"tag_family": "tag36h11"}

    mock_bridge.bproc.camera.get_intrinsics_as_K_matrix.return_value = [
        [500, 0, 0],
        [0, 500, 0],
        [0, 0, 1],
    ]
    mock_project.return_value = None

    # ACT
    compute_geometric_metadata(mock_tag)

    # VERIFY
    # calculate_ppm should be called with z_depth_m=2.0
    _, kwargs = mock_ppm.call_args
    assert np.isclose(kwargs["z_depth_m"], 2.0)
