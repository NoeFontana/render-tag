from __future__ import annotations

import pytest

from render_tag.generation.board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
    validate_board_is_centered,
)


def test_charuco_layout_is_centered_at_origin():
    """
    Test that ChArUco layout is centered at (0,0,0) by default.
    """
    spec = BoardSpec(
        rows=4, cols=6, square_size=0.1, marker_margin=0.01, board_type=BoardType.CHARUCO
    )
    layout = compute_charuco_layout(spec, center=(0, 0, 0))

    is_valid, msg = validate_board_is_centered(layout)
    assert is_valid, f"ChArUco board should be centered at (0,0,0): {msg}"

    # Check bounds
    xs = [p.x for p in layout.tag_positions]
    ys = [p.y for p in layout.tag_positions]

    # For a 4x6 board with 0.1 square size, width=0.6, height=0.4
    # Top-left cell center should be at (-0.25, 0.15)
    # Bottom-right cell center should be at (0.25, -0.15)
    assert min(xs) == pytest.approx(-0.25)
    assert max(xs) == pytest.approx(0.25)
    assert min(ys) == pytest.approx(-0.15)
    assert max(ys) == pytest.approx(0.15)


def test_aprilgrid_layout_is_centered_at_origin():
    """
    Test that AprilGrid layout is centered at (0,0,0) by default.
    """
    spec = BoardSpec(
        rows=4, cols=6, square_size=0.1, marker_margin=0.01, board_type=BoardType.APRILGRID
    )
    layout = compute_aprilgrid_layout(spec, center=(0, 0, 0))

    is_valid, msg = validate_board_is_centered(layout)
    assert is_valid, f"AprilGrid board should be centered at (0,0,0): {msg}"

    # Check corner bounds
    cxs = [p.x for p in layout.corner_positions]
    cys = [p.y for p in layout.corner_positions]

    # Corners are at grid intersections. For 4 rows, 6 cols, width=0.6, height=0.4
    # Corners should range from -0.3 to 0.3 in X, and -0.2 to 0.2 in Y
    assert min(cxs) == pytest.approx(-0.3)
    assert max(cxs) == pytest.approx(0.3)
    assert min(cys) == pytest.approx(-0.2)
    assert max(cys) == pytest.approx(0.2)


def test_cv_space_y_down_invariant():
    """
    Test that the layout generator strictly follows the CV invariant:
    Moving from Row 0 downwards geometrically increases the local Y coordinate.
    """
    spec = BoardSpec(
        rows=3, cols=3, square_size=0.1, marker_margin=0.01, board_type=BoardType.APRILGRID
    )
    layout = compute_aprilgrid_layout(spec, center=(0, 0, 0))

    r0_squares = [sq for sq in layout.squares if sq.row == 0]
    r1_squares = [sq for sq in layout.squares if sq.row == 1]
    r2_squares = [sq for sq in layout.squares if sq.row == 2]

    assert len(r0_squares) == 3
    assert len(r1_squares) == 3
    assert len(r2_squares) == 3

    # Y should increase as we go down the rows
    y0 = r0_squares[0].center.y
    y1 = r1_squares[0].center.y
    y2 = r2_squares[0].center.y

    assert y1 > y0, f"CV Invariant failed: row 1 Y ({y1}) is not > row 0 Y ({y0})"
    assert y2 > y1, f"CV Invariant failed: row 2 Y ({y2}) is not > row 1 Y ({y1})"

    # X should increase as we go across the columns
    x0 = r0_squares[0].center.x
    x1 = r0_squares[1].center.x
    x2 = r0_squares[2].center.x

    assert x1 > x0, f"CV Invariant failed: col 1 X ({x1}) is not > col 0 X ({x0})"
    assert x2 > x1, f"CV Invariant failed: col 2 X ({x2}) is not > col 1 X ({x1})"
