import pytest

from render_tag.generation.intrinsics import resolve_intrinsics


def test_resolve_intrinsics_baked():
    """Test extraction of baked intrinsics."""
    k_matrix = [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]]
    recipe = {"intrinsics": {"resolution": [1920, 1080], "k_matrix": k_matrix}}
    params = resolve_intrinsics(recipe)
    assert params["resolution"] == [1920, 1080]
    assert params["fx"] == 1000.0
    assert params["fy"] == 1000.0
    assert params["cx"] == 960.0
    assert params["cy"] == 540.0
    assert params["k_matrix"] == k_matrix


def test_resolve_intrinsics_fallback():
    """Test emergency fallback if k_matrix is missing."""
    recipe = {"intrinsics": {"resolution": [640, 480]}}
    params = resolve_intrinsics(recipe)
    # With 60 deg FOV: fx = 640 / (2 * tan(30)) = 640 / (2 * 0.577) approx 554.25
    assert params["fx"] == pytest.approx(554.25, rel=1e-3)
    assert params["cx"] == 320.0
