import pytest

from render_tag.generation.intrinsics import resolve_intrinsics


def test_resolve_intrinsics_default():
    """Test resolution with default (flat) dictionary format."""
    recipe = {"intrinsics": {"resolution": [1920, 1080], "fov": 70.0}}
    params = resolve_intrinsics(recipe)
    assert params["resolution"] == [1920, 1080]
    assert params["fov"] == 70.0
    # Center principal point by default
    assert params["cx"] == 960.0
    assert params["cy"] == 540.0
    # fx = 1920 / (2 * tan(35 deg)) = 1920 / (2 * 0.7002) approx 1370.97
    assert params["fx"] == pytest.approx(1370.97, rel=1e-3)
    assert params["fy"] == pytest.approx(1370.97, rel=1e-3)


def test_resolve_intrinsics_explicit_focal():
    """Test resolution with explicit focal lengths (double-nested)."""
    recipe = {
        "intrinsics": {
            "resolution": [1280, 720],
            "intrinsics": {
                "focal_length_x": 1000.0,
                "focal_length_y": 1000.0,
                "principal_point_x": 600.0,
                "principal_point_y": 300.0,
            },
        }
    }
    params = resolve_intrinsics(recipe)
    assert params["fx"] == 1000.0
    assert params["fy"] == 1000.0
    assert params["cx"] == 600.0
    assert params["cy"] == 300.0


def test_resolve_intrinsics_k_matrix():
    """Test resolution with a 3x3 K matrix."""
    k_matrix = [[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]]
    recipe = {"intrinsics": {"resolution": [640, 480], "intrinsics": {"k_matrix": k_matrix}}}
    params = resolve_intrinsics(recipe)
    assert params["fx"] == 800.0
    assert params["fy"] == 800.0
    assert params["cx"] == 320.0
    assert params["cy"] == 240.0
    assert params["k_matrix"] == k_matrix


def test_resolve_intrinsics_fallback_top_level():
    """Test fallback to top-level fields (legacy format)."""
    recipe = {"resolution": [800, 600], "fov": 90.0}
    params = resolve_intrinsics(recipe)
    assert params["resolution"] == [800, 600]
    assert params["fov"] == 90.0
    # fx = 800 / (2 * tan(45 deg)) = 800 / (2 * 1.0) = 400.0
    assert params["fx"] == pytest.approx(400.0)
