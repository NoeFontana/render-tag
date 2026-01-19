"""
Tests for Board Geometry - Pure Python validation of board layouts.

These tests verify physical plausibility of calibration boards:
- White border on edges
- Tags fill all available positions (no gaps)
- Geometry invariants (centering, dimensions, no overlaps)

All tests run WITHOUT Blender.
"""

from render_tag.geometry.board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
    validate_aprilgrid_filling,
    validate_board_dimensions,
    validate_board_is_centered,
    validate_board_plausibility,
    validate_charuco_tag_filling,
    validate_charuco_white_border,
    validate_marker_fits_in_square,
    validate_no_overlaps,
)


# ============================================================================
# BoardSpec Tests
# ============================================================================


class TestBoardSpec:
    """Test BoardSpec computed properties."""

    def test_board_dimensions(self) -> None:
        """Board dimensions = rows * cols * square_size."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)

        assert spec.board_width == 8 * 0.05  # cols * size
        assert spec.board_height == 6 * 0.05  # rows * size

    def test_marker_size_with_margin(self) -> None:
        """Marker size accounts for margin on both sides."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.10, marker_margin=0.01)

        # marker_size = square_size - 2 * margin
        assert spec.marker_size == 0.10 - 2 * 0.01
        assert spec.marker_size == 0.08

    def test_total_squares(self) -> None:
        """Total squares = rows * cols."""
        spec = BoardSpec(rows=5, cols=7, square_size=0.05)

        assert spec.total_squares == 5 * 7

    def test_charuco_white_square_count(self) -> None:
        """ChArUco white squares = ceil(total/2)."""
        # Even total
        spec_even = BoardSpec(rows=6, cols=8, square_size=0.05)
        assert spec_even.white_square_count == 24  # 48/2

        # Odd total
        spec_odd = BoardSpec(rows=5, cols=7, square_size=0.05)
        assert spec_odd.white_square_count == 18  # (35+1)/2 = 18

    def test_expected_tag_count_charuco(self) -> None:
        """ChArUco tag count = white square count."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05, board_type=BoardType.CHARUCO)
        assert spec.expected_tag_count == spec.white_square_count

    def test_expected_tag_count_aprilgrid(self) -> None:
        """AprilGrid tag count = total squares."""
        spec = BoardSpec(
            rows=6, cols=8, square_size=0.05, board_type=BoardType.APRILGRID
        )
        assert spec.expected_tag_count == spec.total_squares

    def test_corner_count_aprilgrid(self) -> None:
        """Corner count = (rows+1) * (cols+1)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        assert spec.corner_count == 7 * 9  # (6+1) * (8+1) = 63


# ============================================================================
# ChArUco Layout Tests
# ============================================================================


class TestCharucoLayout:
    """Test ChArUco board layout generation."""

    def test_charuco_generates_correct_square_count(self) -> None:
        """Layout should have rows * cols squares."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 48

    def test_charuco_generates_correct_tag_count(self) -> None:
        """Layout should have white_square_count tags."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.tag_positions) == spec.white_square_count

    def test_charuco_alternating_pattern(self) -> None:
        """Tags only in (row+col) % 2 == 0 positions."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1)
        layout = compute_charuco_layout(spec)

        for sq in layout.squares:
            expected_white = (sq.row + sq.col) % 2 == 0
            assert sq.is_white == expected_white, (
                f"Square ({sq.row},{sq.col}) has wrong color"
            )
            assert sq.has_tag == expected_white, (
                f"Square ({sq.row},{sq.col}) tag status wrong"
            )

    def test_charuco_has_white_border(self) -> None:
        """All corner squares should have same color (consistent border)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_charuco_white_border(layout)
        assert is_valid, msg

    def test_charuco_maximizes_tags(self) -> None:
        """All white squares should have tags (no gaps)."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_charuco_tag_ids_are_sequential(self) -> None:
        """Tag IDs should be 0, 1, 2, ... in order."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1)
        layout = compute_charuco_layout(spec)

        tag_ids = [sq.tag_id for sq in layout.squares if sq.has_tag]
        expected_ids = list(range(len(tag_ids)))

        assert tag_ids == expected_ids, f"Tag IDs {tag_ids} != expected {expected_ids}"


# ============================================================================
# AprilGrid Layout Tests
# ============================================================================


class TestAprilGridLayout:
    """Test AprilGrid board layout generation."""

    def test_aprilgrid_fills_all_cells(self) -> None:
        """Every cell should have a tag."""
        spec = BoardSpec(
            rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID
        )
        layout = compute_aprilgrid_layout(spec)

        is_valid, msg = validate_aprilgrid_filling(layout)
        assert is_valid, msg

    def test_aprilgrid_tag_count(self) -> None:
        """Tag count should equal total cells."""
        spec = BoardSpec(
            rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID
        )
        layout = compute_aprilgrid_layout(spec)

        assert len(layout.tag_positions) == 5 * 7

    def test_aprilgrid_corner_count(self) -> None:
        """Corner count should be (rows+1) * (cols+1)."""
        spec = BoardSpec(
            rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID
        )
        layout = compute_aprilgrid_layout(spec)

        assert len(layout.corner_positions) == 6 * 8  # (5+1) * (7+1) = 48

    def test_aprilgrid_positions_form_regular_grid(self) -> None:
        """Tag positions should form a regular grid with uniform spacing."""
        spec = BoardSpec(
            rows=4, cols=4, square_size=0.1, board_type=BoardType.APRILGRID
        )
        layout = compute_aprilgrid_layout(spec)

        # Check that horizontal spacing is uniform
        xs = sorted(set(p.x for p in layout.tag_positions))
        for i in range(1, len(xs)):
            spacing = xs[i] - xs[i - 1]
            assert abs(spacing - spec.square_size) < 1e-9, (
                f"Irregular x spacing: {spacing}"
            )

        # Check that vertical spacing is uniform
        ys = sorted(set(p.y for p in layout.tag_positions))
        for i in range(1, len(ys)):
            spacing = ys[i] - ys[i - 1]
            assert abs(spacing - spec.square_size) < 1e-9, (
                f"Irregular y spacing: {spacing}"
            )


# ============================================================================
# Geometry Invariant Tests
# ============================================================================


class TestGeometryInvariants:
    """Test geometry invariants for all board types."""

    def test_board_is_centered_charuco(self) -> None:
        """ChArUco board should be centered at requested center."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec, center=(1.0, 2.0, 0.5))

        is_valid, msg = validate_board_is_centered(layout)
        assert is_valid, msg

    def test_board_is_centered_aprilgrid(self) -> None:
        """AprilGrid board should be centered at requested center."""
        spec = BoardSpec(
            rows=5, cols=7, square_size=0.05, board_type=BoardType.APRILGRID
        )
        layout = compute_aprilgrid_layout(spec, center=(-0.5, 0.5, 0.0))

        is_valid, msg = validate_board_is_centered(layout)
        assert is_valid, msg

    def test_board_dimensions_correct(self) -> None:
        """Board should have expected width/height."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_board_dimensions(layout)
        assert is_valid, msg

    def test_no_overlapping_tags(self) -> None:
        """Tags should not overlap each other."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.01)
        layout = compute_charuco_layout(spec)

        is_valid, msg = validate_no_overlaps(layout)
        assert is_valid, msg

    def test_marker_fits_in_square_valid(self) -> None:
        """Marker should fit within square with margin."""
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.01)

        is_valid, msg = validate_marker_fits_in_square(spec)
        assert is_valid, msg

    def test_marker_fits_in_square_invalid(self) -> None:
        """Detect when marker doesn't fit (margin too large)."""
        # Margin is half the square size, so marker_size = 0
        spec = BoardSpec(rows=4, cols=4, square_size=0.1, marker_margin=0.05)

        is_valid, msg = validate_marker_fits_in_square(spec)
        # This should still pass since 0.1 - 2*0.05 = 0 which is not positive
        # Actually spec.marker_size = 0 which fails the "must be positive" check
        assert not is_valid


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_row_charuco(self) -> None:
        """Single row board should work."""
        spec = BoardSpec(rows=1, cols=8, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 8
        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_single_column_charuco(self) -> None:
        """Single column board should work."""
        spec = BoardSpec(rows=6, cols=1, square_size=0.05)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 6
        is_valid, msg = validate_charuco_tag_filling(layout)
        assert is_valid, msg

    def test_minimal_2x2_charuco(self) -> None:
        """Minimal 2x2 board should work."""
        spec = BoardSpec(rows=2, cols=2, square_size=0.1)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 4
        assert len(layout.tag_positions) == 2  # 2 white squares

    def test_large_board(self) -> None:
        """Large board should work without issues."""
        spec = BoardSpec(rows=20, cols=20, square_size=0.02)
        layout = compute_charuco_layout(spec)

        assert len(layout.squares) == 400
        assert len(layout.tag_positions) == 200


# ============================================================================
# Full Validation Suite Tests
# ============================================================================


class TestFullValidation:
    """Test the complete validation suite."""

    def test_plausibility_all_pass_charuco(self) -> None:
        """All plausibility checks should pass for valid ChArUco."""
        spec = BoardSpec(rows=6, cols=8, square_size=0.05, marker_margin=0.005)
        layout = compute_charuco_layout(spec)

        results = validate_board_plausibility(layout)

        for check_name, is_valid, msg in results:
            assert is_valid, f"Check '{check_name}' failed: {msg}"

    def test_plausibility_all_pass_aprilgrid(self) -> None:
        """All plausibility checks should pass for valid AprilGrid."""
        spec = BoardSpec(
            rows=5,
            cols=7,
            square_size=0.05,
            marker_margin=0.005,
            board_type=BoardType.APRILGRID,
        )
        layout = compute_aprilgrid_layout(spec)

        results = validate_board_plausibility(layout)

        for check_name, is_valid, msg in results:
            assert is_valid, f"Check '{check_name}' failed: {msg}"
