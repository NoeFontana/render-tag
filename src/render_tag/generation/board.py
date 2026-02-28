"""
Board Geometry Module for render-tag.

Pure-Python geometry calculations for calibration board layouts.
This module has NO Blender dependencies and can be tested independently.

Supports:
- ChArUco boards (checkerboard with ArUco markers in white squares)
- AprilGrid boards (Kalibr-style grid with tags in every cell)
"""

from dataclasses import dataclass, field
from enum import Enum


class BoardType(Enum):
    """Type of calibration board."""

    CHARUCO = "charuco"
    APRILGRID = "aprilgrid"


class BoardFrameConstants:
    """Constants for the Canonical Board Coordinate System.
    
    Standardized for Computer Vision (CV) compatibility:
    - Origin (0,0,0) is at the TOP-LEFT corner of the board.
    - X-axis increases from LEFT to RIGHT (Columns 0 to C).
    - Y-axis decreases from TOP to BOTTOM (Rows 0 to R) in Blender local space.
    """
    ROW_ORIGIN_TOP = True  # Row 0 is at the top (+Y)
    COL_ORIGIN_LEFT = True  # Col 0 is at the left (-X)
    Y_DOWN = True           # Moving from Row 0 to Row R decreases Y


@dataclass
class BoardPosition:
    """A position on the board (tag center or corner)."""

    x: float
    y: float
    z: float = 0.0

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class SquareInfo:
    """Information about a square in the board grid."""

    row: int
    col: int
    center: BoardPosition
    is_white: bool  # True = white square (where tags go in ChArUco)
    has_tag: bool = False
    tag_id: int | None = None


@dataclass
class BoardSpec:
    """Specification for a calibration board."""

    rows: int
    cols: int
    square_size: float  # Size of each grid cell in meters
    marker_margin: float = 0.01  # Margin between marker and cell edge
    board_type: BoardType = BoardType.CHARUCO

    # Computed properties
    @property
    def board_width(self) -> float:
        return self.cols * self.square_size

    @property
    def board_height(self) -> float:
        return self.rows * self.square_size

    @property
    def marker_size(self) -> float:
        """Size of the tag/marker after accounting for margin."""
        return self.square_size - 2 * self.marker_margin

    @property
    def total_squares(self) -> int:
        return self.rows * self.cols

    @property
    def white_square_count(self) -> int:
        """Number of white squares (for ChArUco, these hold tags)."""
        # In a checkerboard, white squares are (row+col) % 2 == 0
        # For an MxN board: ceil(M*N/2)
        return (self.total_squares + 1) // 2

    @property
    def black_square_count(self) -> int:
        """Number of black squares in ChArUco pattern."""
        return self.total_squares - self.white_square_count

    @property
    def expected_tag_count(self) -> int:
        """Expected number of tags for this board type."""
        if self.board_type == BoardType.CHARUCO:
            return self.white_square_count
        else:  # APRILGRID
            return self.total_squares

    @property
    def corner_count(self) -> int:
        """Number of corner positions (for AprilGrid corner squares)."""
        return (self.rows + 1) * (self.cols + 1)


@dataclass
class BoardLayout:
    """Complete layout of a calibration board."""

    spec: BoardSpec
    squares: list[SquareInfo] = field(default_factory=list)
    tag_positions: list[BoardPosition] = field(default_factory=list)
    corner_positions: list[BoardPosition] = field(default_factory=list)
    center: BoardPosition = field(default_factory=lambda: BoardPosition(0, 0, 0))


def compute_charuco_layout(
    spec: BoardSpec,
    center: tuple[float, float, float] = (0, 0, 0),
) -> BoardLayout:
    """Compute complete ChArUco board layout.

    ChArUco boards have:
    - Alternating black/white squares (checkerboard pattern)
    - Tags in white squares only
    - White border around edges (first row/col is white at corners)

    Args:
        spec: Board specification
        center: Center point of the board

    Returns:
        Complete board layout with positions
    """
    layout = BoardLayout(
        spec=spec,
        center=BoardPosition(*center),
    )

    # Calculate starting position (center of top-left cell)
    # CV-Standard: Row 0 is at the top (+Y in Blender local)
    start_x = center[0] - spec.board_width / 2 + spec.square_size / 2
    start_y = center[1] + spec.board_height / 2 - spec.square_size / 2

    tag_id = 0

    for row in range(spec.rows):
        for col in range(spec.cols):
            x = start_x + col * spec.square_size
            y = start_y - row * spec.square_size
            z = center[2]

            # In standard ChArUco: (row+col) % 2 == 0 are white squares
            is_white = (row + col) % 2 == 0

            square = SquareInfo(
                row=row,
                col=col,
                center=BoardPosition(x, y, z),
                is_white=is_white,
                has_tag=is_white,  # Tags in white squares
                tag_id=tag_id if is_white else None,
            )
            layout.squares.append(square)

            if is_white:
                layout.tag_positions.append(BoardPosition(x, y, z))
                tag_id += 1

    return layout


def compute_aprilgrid_layout(
    spec: BoardSpec,
    corner_size: float = 0.02,
    center: tuple[float, float, float] = (0, 0, 0),
) -> BoardLayout:
    """Compute complete AprilGrid board layout.

    AprilGrid boards have:
    - Tags in every cell
    - Small black corner squares at grid intersections
    - White background/border

    Args:
        spec: Board specification
        corner_size: Size of corner squares
        center: Center point of the board

    Returns:
        Complete board layout with positions
    """
    layout = BoardLayout(
        spec=spec,
        center=BoardPosition(*center),
    )

    # Calculate starting position (center of top-left cell)
    # CV-Standard: Row 0 is at the top (+Y in Blender local)
    start_x = center[0] - spec.board_width / 2 + spec.square_size / 2
    start_y = center[1] + spec.board_height / 2 - spec.square_size / 2

    # All cells have tags in AprilGrid
    tag_id = 0
    for row in range(spec.rows):
        for col in range(spec.cols):
            x = start_x + col * spec.square_size
            y = start_y - row * spec.square_size
            z = center[2]

            square = SquareInfo(
                row=row,
                col=col,
                center=BoardPosition(x, y, z),
                is_white=True,  # All cells are "white" in AprilGrid
                has_tag=True,
                tag_id=tag_id,
            )
            layout.squares.append(square)
            layout.tag_positions.append(BoardPosition(x, y, z))
            tag_id += 1

    # Compute corner positions (at grid intersections)
    corner_start_x = center[0] - spec.board_width / 2
    corner_start_y = center[1] + spec.board_height / 2

    for row in range(spec.rows + 1):
        for col in range(spec.cols + 1):
            x = corner_start_x + col * spec.square_size
            y = corner_start_y - row * spec.square_size
            layout.corner_positions.append(BoardPosition(x, y, center[2]))

    return layout


def validate_charuco_white_border(layout: BoardLayout) -> tuple[bool, str]:
    """Validate that ChArUco board has proper border configuration.

    The standard OpenCV convention is:
    - Square (0,0) is WHITE (contains a tag)
    - This ensures the board has white at the top-left corner (OpenCV convention)
    - The checkerboard pattern means edges alternate, but white is "first"

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not layout.squares:
        return False, "No squares in layout"

    # Find the (0,0) square
    origin_square = None
    for sq in layout.squares:
        if sq.row == 0 and sq.col == 0:
            origin_square = sq
            break

    if origin_square is None:
        return False, "Could not find origin square (0,0)"

    # OpenCV convention: (0,0) should be white
    if not origin_square.is_white:
        return False, "Square (0,0) should be white (OpenCV ChArUco convention)"

    # Verify alternating pattern is consistent
    for sq in layout.squares:
        expected_white = (sq.row + sq.col) % 2 == 0
        if sq.is_white != expected_white:
            return (
                False,
                f"Square ({sq.row},{sq.col}) has wrong color for checkerboard pattern",
            )

    return True, ""


def validate_charuco_tag_filling(layout: BoardLayout) -> tuple[bool, str]:
    """Validate that all white squares have tags (no gaps).

    Returns:
        Tuple of (is_valid, error_message)
    """
    white_squares = [sq for sq in layout.squares if sq.is_white]
    tagged_squares = [sq for sq in layout.squares if sq.has_tag]

    if len(white_squares) != len(tagged_squares):
        return (
            False,
            f"White squares ({len(white_squares)}) != tagged squares ({len(tagged_squares)})",
        )

    # Verify every white square has a tag
    for sq in white_squares:
        if not sq.has_tag:
            return False, f"White square at ({sq.row},{sq.col}) has no tag"

    return True, ""


def validate_aprilgrid_filling(layout: BoardLayout) -> tuple[bool, str]:
    """Validate that all cells have tags (no gaps).

    Returns:
        Tuple of (is_valid, error_message)
    """
    expected_tags = layout.spec.rows * layout.spec.cols
    actual_tags = len(layout.tag_positions)

    if actual_tags != expected_tags:
        return False, f"Expected {expected_tags} tags, found {actual_tags}"

    # Verify every square has a tag
    for sq in layout.squares:
        if not sq.has_tag:
            return False, f"Cell at ({sq.row},{sq.col}) has no tag"

    return True, ""


def validate_no_overlaps(layout: BoardLayout) -> tuple[bool, str]:
    """Validate that no elements overlap.

    Returns:
        Tuple of (is_valid, error_message)
    """
    marker_size = layout.spec.marker_size
    min_distance = marker_size * 0.5  # Half-size = touching edge

    positions = layout.tag_positions

    for i, p1 in enumerate(positions):
        for j, p2 in enumerate(positions):
            if i >= j:
                continue
            dx = p1.x - p2.x
            dy = p1.y - p2.y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < min_distance:
                return (
                    False,
                    f"Tags at positions {i} and {j} overlap (distance={dist:.4f})",
                )

    return True, ""


def validate_board_is_centered(
    layout: BoardLayout,
    tolerance: float = 1e-6,
) -> tuple[bool, str]:
    """Validate that board is centered at the specified center point.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not layout.squares:
        return False, "No squares in layout"

    # Compute actual center from square positions
    xs = [sq.center.x for sq in layout.squares]
    ys = [sq.center.y for sq in layout.squares]

    actual_cx = (min(xs) + max(xs)) / 2
    actual_cy = (min(ys) + max(ys)) / 2

    dx = abs(actual_cx - layout.center.x)
    dy = abs(actual_cy - layout.center.y)

    if dx > tolerance or dy > tolerance:
        return (
            False,
            f"Center ({actual_cx:.4f}, {actual_cy:.4f}) != ({layout.center.x}, {layout.center.y})",
        )

    return True, ""


def validate_board_dimensions(
    layout: BoardLayout,
    tolerance: float = 1e-6,
) -> tuple[bool, str]:
    """Validate that board has expected dimensions.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not layout.squares:
        return False, "No squares in layout"

    xs = [sq.center.x for sq in layout.squares]
    ys = [sq.center.y for sq in layout.squares]

    # Actual width/height (from center to center of edge squares)
    actual_width = max(xs) - min(xs) + layout.spec.square_size
    actual_height = max(ys) - min(ys) + layout.spec.square_size

    expected_width = layout.spec.board_width
    expected_height = layout.spec.board_height

    if abs(actual_width - expected_width) > tolerance:
        return False, f"Board width {actual_width:.4f} != expected {expected_width:.4f}"

    if abs(actual_height - expected_height) > tolerance:
        return (
            False,
            f"Board height {actual_height:.4f} != expected {expected_height:.4f}",
        )

    return True, ""


def validate_marker_fits_in_square(spec: BoardSpec) -> tuple[bool, str]:
    """Validate that marker size is smaller than square (with margin).

    Returns:
        Tuple of (is_valid, error_message)
    """
    if spec.marker_size <= 0:
        return False, f"Marker size ({spec.marker_size}) must be positive"

    if spec.marker_size >= spec.square_size:
        return (
            False,
            f"Marker size ({spec.marker_size}) >= square size ({spec.square_size})",
        )

    if spec.marker_margin < 0:
        return False, f"Margin ({spec.marker_margin}) must be non-negative"

    return True, ""


def validate_board_plausibility(layout: BoardLayout) -> list[tuple[str, bool, str]]:
    """Run all plausibility checks on a board layout.

    Returns:
        List of (check_name, is_valid, error_message) triplets for each check
    """
    results = []

    # Spec-level checks
    results.append(("marker_fits", *validate_marker_fits_in_square(layout.spec)))

    # Layout-level checks
    results.append(("centered", *validate_board_is_centered(layout)))
    results.append(("dimensions", *validate_board_dimensions(layout)))
    results.append(("no_overlaps", *validate_no_overlaps(layout)))

    # Board-type specific checks
    if layout.spec.board_type == BoardType.CHARUCO:
        results.append(("white_border", *validate_charuco_white_border(layout)))
        results.append(("tag_filling", *validate_charuco_tag_filling(layout)))
    else:
        results.append(("tag_filling", *validate_aprilgrid_filling(layout)))

    return results
