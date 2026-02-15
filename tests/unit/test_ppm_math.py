"""
Unit tests for PPM (Pixels Per Module) mathematics.
"""

import pytest

from render_tag.generation.projection_math import calculate_ppm, solve_distance_for_ppm


def test_calculate_ppm():
    # Known scenario:
    # Tag size: 0.16m
    # Tag grid size: 8 bits
    # Focal length: 1000px
    # Distance: 2.0m
    # PPM = (f * tag_size) / (distance * grid_size)
    # PPM = (1000 * 0.16) / (2.0 * 8) = 160 / 16 = 10.0

    ppm = calculate_ppm(distance_m=2.0, tag_size_m=0.16, focal_length_px=1000.0, tag_grid_size=8)
    assert pytest.approx(ppm) == 10.0


def test_solve_distance_for_ppm():
    # Invert the above:
    # Target PPM: 10.0
    # Tag size: 0.16m
    # Tag grid size: 8 bits
    # Focal length: 1000px
    # Distance = (f * tag_size) / (target_ppm * grid_size)
    # Distance = (1000 * 0.16) / (10.0 * 8) = 160 / 80 = 2.0

    distance = solve_distance_for_ppm(
        target_ppm=10.0, tag_size_m=0.16, focal_length_px=1000.0, tag_grid_size=8
    )
    assert pytest.approx(distance) == 2.0


def test_ppm_roundtrip():
    # Ensure they are inverse functions
    dist = 5.43
    size = 0.12
    f = 1200.0
    grid = 10

    ppm = calculate_ppm(dist, size, f, grid)
    solved_dist = solve_distance_for_ppm(ppm, size, f, grid)

    assert pytest.approx(solved_dist) == dist
