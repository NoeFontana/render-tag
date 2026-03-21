"""Tests that the default principal point follows the OpenCV / BlenderProc convention.

The convention is: cx = (W - 1) / 2, cy = (H - 1) / 2, where pixel centers
are at integer coordinates and the center of the image is the midpoint
between the two center pixels.
"""

from __future__ import annotations

import math

import pytest

from render_tag.core.config import CameraConfig, CameraIntrinsics


@pytest.mark.parametrize(
    "width,height",
    [
        (1920, 1080),
        (1280, 720),
        (640, 480),
        (4096, 2160),
        (800, 600),
    ],
)
def test_default_principal_point_convention(width: int, height: int):
    """Default principal point must be W/2, H/2 for centered cameras."""
    config = CameraConfig(resolution=(width, height), fov=70.0)
    k = config.get_k_matrix()

    expected_cx = width / 2.0
    expected_cy = height / 2.0

    assert k[0][2] == pytest.approx(expected_cx), f"cx should be W/2 = {expected_cx}, got {k[0][2]}"
    assert k[1][2] == pytest.approx(expected_cy), f"cy should be H/2 = {expected_cy}, got {k[1][2]}"


def test_explicit_principal_point_overrides_default():
    """Explicit principal_point_x/y should override the default."""
    intrinsics = CameraIntrinsics(
        focal_length=1000.0,
        principal_point_x=100.0,
        principal_point_y=200.0,
    )
    config = CameraConfig(resolution=(1920, 1080), intrinsics=intrinsics)
    k = config.get_k_matrix()

    assert k[0][2] == 100.0
    assert k[1][2] == 200.0


def test_explicit_k_matrix_not_modified():
    """An explicitly provided K matrix should be returned as-is."""
    custom_k = [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
    intrinsics = CameraIntrinsics(k_matrix=custom_k)
    config = CameraConfig(resolution=(640, 480), intrinsics=intrinsics)
    k = config.get_k_matrix()

    assert k == custom_k


def test_focal_length_from_fov():
    """Focal length computed from FOV should be W / (2 * tan(fov/2))."""
    config = CameraConfig(resolution=(1920, 1080), fov=70.0)
    k = config.get_k_matrix()

    expected_fx = 1920 / (2.0 * math.tan(math.radians(35.0)))
    assert k[0][0] == pytest.approx(expected_fx)
    assert k[1][1] == pytest.approx(expected_fx)


def test_camera_fallback_principal_point():
    """The emergency fallback in camera.py should also use W/2 convention."""
    from unittest.mock import MagicMock, patch

    import numpy as np

    mock_bridge = MagicMock()
    mock_bridge.np = np

    from render_tag.core.schema.recipe import CameraRecipe

    camera_recipe = CameraRecipe(
        transform_matrix=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        intrinsics={"resolution": [1920, 1080], "k_matrix": [], "fov": 70.0},
    )

    with patch("render_tag.backend.camera.bridge", mock_bridge):
        from render_tag.backend.camera import set_camera_intrinsics

        set_camera_intrinsics(camera_recipe)

    # The K matrix passed to set_intrinsics_from_K_matrix should have cx=959.5 because
    # camera.py subtracts 0.5 to counteract BlenderProc's automatic sensor shift.
    call_args = mock_bridge.bproc.camera.set_intrinsics_from_K_matrix.call_args
    k_passed = call_args.kwargs.get("K") or call_args[1].get("K") or call_args[0][0]

    assert k_passed[0][2] == pytest.approx(959.5), (
        f"Fallback cx passed to BlenderProc should be 959.5, got {k_passed[0][2]}"
    )
    assert k_passed[1][2] == pytest.approx(539.5), (
        f"Fallback cy passed to BlenderProc should be 539.5, got {k_passed[1][2]}"
    )
