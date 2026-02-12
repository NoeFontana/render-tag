"""
Advanced unit tests for board geometry, focusing on malformed specs and failures.
"""

from render_tag.geometry.board import (
    BoardLayout,
    BoardPosition,
    BoardSpec,
    compute_charuco_layout,
    validate_board_dimensions,
    validate_board_is_centered,
    validate_marker_fits_in_square,
)


def test_invalid_marker_fits():
    # Marker larger than square
    spec = BoardSpec(rows=2, cols=2, square_size=0.1, marker_margin=-0.01)
    # marker_size = 0.1 - 2*(-0.01) = 0.12 > 0.1
    is_valid, msg = validate_marker_fits_in_square(spec)
    assert not is_valid
    assert "marker_margin" in msg or "Marker size" in msg

    # Zero/Negative marker size
    spec = BoardSpec(rows=2, cols=2, square_size=0.1, marker_margin=0.06)
    # marker_size = 0.1 - 0.12 = -0.02
    is_valid, msg = validate_marker_fits_in_square(spec)
    assert not is_valid
    assert "positive" in msg


def test_board_dimension_validation_failure():
    spec = BoardSpec(rows=4, cols=4, square_size=0.1)
    layout = compute_charuco_layout(spec)

    # Manually tamper with spec to make it inconsistent with layout
    layout.spec = BoardSpec(rows=4, cols=4, square_size=0.2)

    is_valid, msg = validate_board_dimensions(layout)
    assert not is_valid
    assert "width" in msg or "height" in msg


def test_board_centering_validation_failure():
    spec = BoardSpec(rows=4, cols=4, square_size=0.1)
    layout = compute_charuco_layout(spec, center=(0, 0, 0))

    # Tamper with center
    layout.center = BoardPosition(1.0, 1.0, 0.0)

    is_valid, msg = validate_board_is_centered(layout)
    assert not is_valid
    assert "Center" in msg


def test_empty_layout_validation():
    spec = BoardSpec(rows=0, cols=0, square_size=0.1)
    layout = BoardLayout(spec=spec)

    is_valid, msg = validate_board_is_centered(layout)
    assert not is_valid
    assert "No squares" in msg

    is_valid, msg = validate_board_dimensions(layout)
    assert not is_valid
    assert "No squares" in msg
