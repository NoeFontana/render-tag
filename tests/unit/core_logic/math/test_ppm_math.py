import numpy as np
import pytest

from render_tag.core.geometry.projection_math import calculate_ppm, solve_distance_for_ppm


def test_calculate_ppm():
    # distance = 1.0m, tag_size = 0.1m, f_px = 1000px, grid_size = 10
    # PPM = (1000 * 0.1) / (1.0 * 10) = 100 / 10 = 10
    ppm = calculate_ppm(z_depth_m=1.0, tag_size_m=0.1, focal_length_px=1000.0, tag_grid_size=10)
    assert ppm == pytest.approx(10.0)

    # distance = 2.0m -> PPM should be 5
    ppm = calculate_ppm(z_depth_m=2.0, tag_size_m=0.1, focal_length_px=1000.0, tag_grid_size=10)
    assert ppm == pytest.approx(5.0)


def test_solve_distance_for_ppm():
    # target_ppm = 10, tag_size = 0.1m, f_px = 1000px, grid_size = 10
    # distance = (1000 * 0.1) / (10 * 10) = 100 / 100 = 1.0
    dist = solve_distance_for_ppm(
        target_ppm=10.0, tag_size_m=0.1, focal_length_px=1000.0, tag_grid_size=10
    )
    assert dist == pytest.approx(1.0)

    # target_ppm = 5 -> distance should be 2.0
    dist = solve_distance_for_ppm(
        target_ppm=5.0, tag_size_m=0.1, focal_length_px=1000.0, tag_grid_size=10
    )
    assert dist == pytest.approx(2.0)


def test_ppm_roundtrip():
    rng = np.random.default_rng(42)
    for _ in range(100):
        target_ppm = rng.uniform(5, 100)
        tag_size = rng.uniform(0.05, 0.5)
        f_px = rng.uniform(500, 2000)
        grid_size = int(rng.integers(6, 12))

        dist = solve_distance_for_ppm(target_ppm, tag_size, f_px, grid_size)
        actual_ppm = calculate_ppm(
            z_depth_m=dist, tag_size_m=tag_size, focal_length_px=f_px, tag_grid_size=grid_size
        )

        assert actual_ppm == pytest.approx(target_ppm)
