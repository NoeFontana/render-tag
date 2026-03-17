import hashlib
import json
from math import ceil
from pathlib import Path

import cv2
import numpy as np

from ..core.constants import TAG_GRID_SIZES
from ..core.schema.board import BoardConfig, BoardType
from .tags import generate_tag_image


class TextureFactory:
    """Sub-pixel accurate calibration target texture synthesizer."""

    def __init__(self, px_per_mm: float = 50.0, cache_dir: Path | None = None):
        """
        Args:
            px_per_mm: Resolution of the generated texture (default: 50px/mm).
                Higher density pushes aliasing artifacts beyond the Nyquist limit
                of simulated camera sensors, preserving geometrically true gradients
                at tag corners when projected onto slanted 3D planes.
            cache_dir: Optional directory to cache generated textures
        """
        self.px_per_mm = px_per_mm
        self.px_per_m = px_per_mm * 1000.0
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_board_texture(self, config: BoardConfig) -> np.ndarray:
        """Generate a high-resolution texture for a calibration board.

        Args:
            config: The board configuration

        Returns:
            A grayscale numpy array containing the generated texture
        """
        # 1. Check Cache
        cache_path = None
        if self.cache_dir:
            config_hash = self._calculate_hash(config)
            cache_path = self.cache_dir / f"board_{config_hash}.png"
            if cache_path.exists():
                cached = cv2.imread(str(cache_path), cv2.IMREAD_GRAYSCALE)
                if cached is not None:
                    return cached

        # 2. Calculate Dimensions
        if config.type == BoardType.APRILGRID:
            # AprilGrid: square_size = marker_size * (1 + spacing_ratio)
            assert config.spacing_ratio is not None
            square_size = config.marker_size * (1.0 + config.spacing_ratio)
        else:
            # ChArUco: square_size is explicit
            assert config.square_size is not None
            square_size = config.square_size

        width_m = config.cols * square_size
        height_m = config.rows * square_size

        # Snap marker_px UP to the next multiple of the tag grid size so that
        # every data-bit module occupies an identical number of pixels.
        # generate_tag_image snaps DOWN internally, so we must align upward here
        # to guarantee k*N pixels are requested — ensuring zero aliasing in the
        # internal bit grid before perspective warp.
        grid_size = TAG_GRID_SIZES.get(config.dictionary, 8)
        marker_px_f_nom = config.marker_size * self.px_per_m
        marker_px = ceil(marker_px_f_nom / grid_size) * grid_size

        # Derive an effective resolution from the snapped marker size and scale all
        # other dimensions proportionally so spatial relationships remain correct.
        effective_px_per_m = marker_px / config.marker_size

        quiet_zone_px = round(config.quiet_zone_m * effective_px_per_m)

        width_px = round(width_m * effective_px_per_m) + 2 * quiet_zone_px
        height_px = round(height_m * effective_px_per_m) + 2 * quiet_zone_px

        # Keep as continuous floats to preserve sub-pixel placement accuracy
        square_px_f = square_size * effective_px_per_m

        # 3. Initialize Image (White background)
        img = np.full((height_px, width_px), 255, dtype=np.uint8)

        # 4. Draw Board Content
        if config.type == BoardType.CHARUCO:
            self._draw_charuco(img, config, square_px_f, marker_px, quiet_zone_px)
        elif config.type == BoardType.APRILGRID:
            self._draw_aprilgrid(img, config, square_px_f, marker_px, quiet_zone_px)

        # 5. Save to Cache
        if cache_path:
            cv2.imwrite(str(cache_path), img)

        return img

    def _composite_tag_subpixel(
        self,
        canvas: np.ndarray,
        tag_img: np.ndarray,
        center_x: float,
        center_y: float,
        interpolation: int = cv2.INTER_CUBIC,
    ) -> None:
        """Composite a tag onto the canvas at a sub-pixel accurate position.

        Builds an affine translation matrix that maps the tag center to the
        continuous (center_x, center_y) coordinate on the canvas. The affine
        warp with bicubic interpolation produces smooth sub-pixel gradients at
        tag edges, which is geometrically faithful for detector refinement tests.

        The result is composited via element-wise minimum so dark tag pixels
        are never brightened by the white canvas background.

        Args:
            canvas: Target image array (modified in-place).
            tag_img: Tag image to composite (grayscale uint8).
            center_x: Continuous x coordinate of the tag center on the canvas.
            center_y: Continuous y coordinate of the tag center on the canvas.
            interpolation: OpenCV interpolation flag for the affine warp.
        """
        tag_h, tag_w = tag_img.shape[:2]

        # Translation: map tag center to the target canvas position
        tx = center_x - tag_w / 2.0
        ty = center_y - tag_h / 2.0

        M = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty]], dtype=np.float64)

        # Warp tag into a temporary canvas-sized image (white background)
        warped = cv2.warpAffine(
            tag_img.astype(np.float32),
            M,
            (canvas.shape[1], canvas.shape[0]),
            flags=interpolation,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255.0,
        )

        # Composite: minimum preserves dark tag pixels over the white background
        np.minimum(canvas, np.round(warped).astype(np.uint8), out=canvas)

    def _draw_charuco(
        self,
        img: np.ndarray,
        config: BoardConfig,
        square_px_f: float,
        marker_px: int,
        quiet_zone_px: int = 0,
    ) -> None:
        """Draw a ChArUco checkerboard pattern.

        Cell boundaries are kept as continuous floats so the tag center
        coordinates are exact; only the background square fills are rounded
        to integer pixel indices.

        Args:
            img: The target image array.
            config: The board configuration.
            square_px_f: Floating-point cell size in pixels.
            marker_px: Marker size in pixels (pre-snapped to grid_size multiple).
            quiet_zone_px: White border width in pixels around the grid.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0

        for r in range(rows):
            for c in range(cols):
                # Checkerboard pattern: (0,0) is white in OpenCV ChArUco convention
                is_white = (r + c) % 2 == 0

                # Continuous floating-point cell boundaries, offset by quiet zone
                y0_f = r * square_px_f + quiet_zone_px
                x0_f = c * square_px_f + quiet_zone_px
                y1_f = (r + 1) * square_px_f + quiet_zone_px
                x1_f = (c + 1) * square_px_f + quiet_zone_px

                # Integer pixel boundaries for square fills
                iy0 = round(y0_f)
                ix0 = round(x0_f)
                iy1 = round(y1_f) if (r < rows - 1 or quiet_zone_px > 0) else img.shape[0]
                ix1 = round(x1_f) if (c < cols - 1 or quiet_zone_px > 0) else img.shape[1]

                if not is_white:
                    img[iy0:iy1, ix0:ix1] = 0
                else:
                    tag_img = generate_tag_image(
                        family=config.dictionary,
                        tag_id=tag_id,
                        size_pixels=marker_px,
                        border_bits=1,
                    )
                    if tag_img is not None:
                        # Sub-pixel accurate center: exact midpoint of the continuous cell
                        center_x = (x0_f + x1_f) / 2.0
                        center_y = (y0_f + y1_f) / 2.0
                        self._composite_tag_subpixel(img, tag_img, center_x, center_y)
                    tag_id += 1

    def _draw_aprilgrid(
        self,
        img: np.ndarray,
        config: BoardConfig,
        square_px_f: float,
        marker_px: int,
        quiet_zone_px: int = 0,
    ) -> None:
        """Draw an AprilGrid pattern (tags in every cell + corner squares).

        Cell boundaries are kept as continuous floats so the tag center
        coordinates are exact. Corner square sizes are driven by
        ``config.kalibr_corner_ratio`` (defaulting to 0.1) and their centers
        are placed at the exact continuous grid intersection, guaranteeing
        symmetric pixel fills for Harris saddle-point accuracy.

        Args:
            img: The target image array.
            config: The board configuration.
            square_px_f: Floating-point cell size in pixels.
            marker_px: Marker size in pixels (pre-snapped to grid_size multiple).
            quiet_zone_px: White border width in pixels around the grid.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0

        for r in range(rows):
            for c in range(cols):
                # Continuous floating-point cell boundaries, offset by quiet zone
                y0_f = r * square_px_f + quiet_zone_px
                x0_f = c * square_px_f + quiet_zone_px
                y1_f = (r + 1) * square_px_f + quiet_zone_px
                x1_f = (c + 1) * square_px_f + quiet_zone_px

                tag_img = generate_tag_image(
                    family=config.dictionary,
                    tag_id=tag_id,
                    size_pixels=marker_px,
                    border_bits=1,
                )
                if tag_img is not None:
                    # Sub-pixel accurate center: exact midpoint of the continuous cell
                    center_x = (x0_f + x1_f) / 2.0
                    center_y = (y0_f + y1_f) / 2.0
                    self._composite_tag_subpixel(img, tag_img, center_x, center_y)
                tag_id += 1

        # Draw black corner squares (AprilGrid characteristic) at grid intersections.
        # corner_px is forced to an even integer so that integer offsets from the
        # rounded center are symmetric on both sides — eliminating the half-to-even
        # rounding asymmetry that produced inconsistent corner sizes and, at the
        # extremes, zero-width squares when corner_half == 0.5.
        corner_ratio = config.kalibr_corner_ratio if config.kalibr_corner_ratio is not None else 0.1
        corner_px = max(2, int(marker_px * corner_ratio) & ~1)
        corner_half = corner_px // 2
        for r in range(rows + 1):
            for c in range(cols + 1):
                y_f = r * square_px_f + quiet_zone_px
                x_f = c * square_px_f + quiet_zone_px

                cy = round(y_f)
                cx = round(x_f)
                cy0 = max(quiet_zone_px, cy - corner_half)
                cy1 = min(img.shape[0] - quiet_zone_px, cy + corner_half)
                cx0 = max(quiet_zone_px, cx - corner_half)
                cx1 = min(img.shape[1] - quiet_zone_px, cx + corner_half)

                img[cy0:cy1, cx0:cx1] = 0

    def _calculate_hash(self, config: BoardConfig) -> str:
        """Calculate a unique hash for a board configuration.

        Args:
            config: The board configuration.

        Returns:
            A SHA256 hash string.
        """
        data = config.model_dump()
        data["px_per_mm"] = self.px_per_mm
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
