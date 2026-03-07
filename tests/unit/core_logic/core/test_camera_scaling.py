import pytest

from render_tag.core.config import CameraConfig, CameraIntrinsics


def test_camera_scaling():
    # Base 1080p camera
    intrinsics = CameraIntrinsics(
        focal_length_x=1000.0,
        focal_length_y=1000.0,
        principal_point_x=960.0,
        principal_point_y=540.0,
    )
    config = CameraConfig(resolution=(1920, 1080), intrinsics=intrinsics)

    # Scale to 4K (3840x2160) - 2x scale
    config.scale_resolution(3840, 2160)

    assert config.resolution == (3840, 2160)
    assert config.intrinsics.focal_length_x == 2000.0
    assert config.intrinsics.focal_length_y == 2000.0
    assert config.intrinsics.principal_point_x == 1920.0
    assert config.intrinsics.principal_point_y == 1080.0


def test_camera_scaling_k_matrix():
    k_matrix = [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]]
    intrinsics = CameraIntrinsics(k_matrix=k_matrix)
    config = CameraConfig(resolution=(1920, 1080), intrinsics=intrinsics)

    config.scale_resolution(1280, 720)  # 2/3 scale

    scaled_k = config.intrinsics.k_matrix
    assert scaled_k is not None
    assert pytest.approx(scaled_k[0][0]) == 1000.0 * (1280 / 1920)
    assert pytest.approx(scaled_k[1][1]) == 1000.0 * (720 / 1080)
    assert pytest.approx(scaled_k[0][2]) == 960.0 * (1280 / 1920)
    assert pytest.approx(scaled_k[1][2]) == 540.0 * (720 / 1080)


def test_camera_scaling_aspect_ratio_error():
    config = CameraConfig(resolution=(1920, 1080))
    # Test changing aspect ratio (which should be allowed, but scales X and Y independently)
    config.scale_resolution(1080, 1920)
    assert config.resolution == (1080, 1920)


def test_camera_scaling_via_override():
    from pathlib import Path

    from render_tag.core.config_loader import ConfigResolver

    resolver = ConfigResolver()

    # We test overriding resolution via string
    overrides = {"camera.resolution": "[3840, 2160]"}
    spec = resolver.resolve(output_dir=Path("/tmp/out"), overrides=overrides)

    assert spec.scene_config.camera.resolution == (3840, 2160)

    # In default config, it's computed from FOV because K is None. Let's provide a K matrix first.
