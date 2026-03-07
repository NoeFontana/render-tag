import pytest

from render_tag.generation.board import (
    BoardLayout,
    BoardPosition,
    BoardSpec,
    validate_no_overlaps,
)


def test_validate_no_overlaps_fails_on_partial_overlap():
    """
    Test that the current validate_no_overlaps implementation
    incorrectly passes when tags overlap by up to 50%.
    """
    # Minimum distance should be marker_size (0.1), but current code uses 0.05

    # Create a spec with marker_size = 0.1
    spec = BoardSpec(rows=2, cols=2, square_size=0.12, marker_margin=0.01)
    assert spec.marker_size == pytest.approx(0.1)

    layout = BoardLayout(spec=spec)
    # Tag 1 at origin
    layout.tag_positions.append(BoardPosition(0.0, 0.0))
    # Tag 2 at (0.07, 0.0), overlapping by 0.03m (30% overlap)
    # Current code check: 0.07 < 0.05? False -> Passes (WRONG)
    layout.tag_positions.append(BoardPosition(0.07, 0.0))

    is_valid, msg = validate_no_overlaps(layout)

    # NEW implementation should correctly reject this
    assert not is_valid, f"Overlapping tags (0.07m apart, size 0.1m) should be rejected. {msg}"
    assert "overlap" in msg.lower()


def test_validate_no_overlaps_strict():
    """
    Placeholder for the CORRECTED implementation.
    """
    pass
