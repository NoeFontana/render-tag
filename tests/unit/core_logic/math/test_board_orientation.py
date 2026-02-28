"""
Tests for Board Orientation and Coordinate System synchronization.
Ensures that Row 0 is at the TOP (+Y) and Col 0 is at the LEFT (-X).
"""

import pytest

from render_tag.generation.board import (
    BoardSpec,
    BoardType,
    compute_aprilgrid_layout,
    compute_charuco_layout,
)


class TestBoardOrientation:
    """Verify that board layouts follow the CV-standard (Top-Left origin)."""

    @pytest.mark.parametrize("board_type", [BoardType.CHARUCO, BoardType.APRILGRID])
    def test_row_0_is_above_row_1(self, board_type: BoardType):
        """Row 0 should have a higher Y coordinate than Row 1 (Top-Down)."""
        spec = BoardSpec(rows=2, cols=2, square_size=0.1, board_type=board_type)

        if board_type == BoardType.CHARUCO:
            layout = compute_charuco_layout(spec, center=(0, 0, 0))
        else:
            layout = compute_aprilgrid_layout(spec, center=(0, 0, 0))

        # Get squares for Row 0 and Row 1
        row0_squares = [sq for sq in layout.squares if sq.row == 0]
        row1_squares = [sq for sq in layout.squares if sq.row == 1]

        assert len(row0_squares) == 2
        assert len(row1_squares) == 2

        y0 = row0_squares[0].center.y
        y1 = row1_squares[0].center.y

        # CURRENTLY FAILS: y0 (-0.05) < y1 (0.05)
        assert y0 > y1, f"Row 0 Y ({y0}) should be > Row 1 Y ({y1})"

    @pytest.mark.parametrize("board_type", [BoardType.CHARUCO, BoardType.APRILGRID])
    def test_col_0_is_left_of_col_1(self, board_type: BoardType):
        """Col 0 should have a lower X coordinate than Col 1 (Left-to-Right)."""
        spec = BoardSpec(rows=2, cols=2, square_size=0.1, board_type=board_type)

        if board_type == BoardType.CHARUCO:
            layout = compute_charuco_layout(spec, center=(0, 0, 0))
        else:
            layout = compute_aprilgrid_layout(spec, center=(0, 0, 0))

        # Get squares for Col 0 and Col 1
        col0_squares = [sq for sq in layout.squares if sq.col == 0]
        col1_squares = [sq for sq in layout.squares if sq.col == 1]

        x0 = col0_squares[0].center.x
        x1 = col1_squares[0].center.x

        # Should pass: x0 (-0.05) < x1 (0.05)
        assert x0 < x1, f"Col 0 X ({x0}) should be < Col 1 X ({x1})"

    def test_aprilgrid_corners_follow_y_down(self):
        """AprilGrid corners should also follow the Top-Down convention."""
        spec = BoardSpec(rows=2, cols=2, square_size=0.1, board_type=BoardType.APRILGRID)
        layout = compute_aprilgrid_layout(spec, center=(0, 0, 0))

        # Corner grid is (rows+1) x (cols+1) = 3x3
        # In a 2x2 board, Row 0 corners should be at Y=0.1, Row 1 at Y=0.0, Row 2 at Y=-0.1
        # (Assuming board height is 0.2)

        # Currently, they are calculated as:
        # corner_start_y = center[1] - spec.board_height / 2 = -0.1
        # y = corner_start_y + row * spec.square_size
        # Row 0: -0.1, Row 1: 0.0, Row 2: 0.1

        # We want: Row 0: 0.1, Row 1: 0.0, Row 2: -0.1

        # Let's extract Y coordinates for each corner row
        # Since corner_positions is a flat list, we need to know how it's populated.
        # In compute_aprilgrid_layout:
        # for row in range(spec.rows + 1):
        #     for col in range(spec.cols + 1):
        #         layout.corner_positions.append(...)

        row0_y = layout.corner_positions[0].y  # First corner (Row 0, Col 0)
        row1_y = layout.corner_positions[3].y  # Fourth corner (Row 1, Col 0)

        assert row0_y > row1_y, f"Corner Row 0 Y ({row0_y}) should be > Corner Row 1 Y ({row1_y})"
