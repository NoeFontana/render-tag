import hashlib
import json
from math import ceil
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np

from ..core.constants import TAG_GRID_SIZES
from ..core.schema.board import BoardConfig, BoardType
from .tags import generate_tag_image


class GridMetrics(NamedTuple):
    """Resolution parameters derived from a BoardConfig and px_per_m."""

    square_px: int
    marker_px: int
    quiet_zone_px: int
    effective_px_per_m: float


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

    def compute_grid_metrics(self, config: BoardConfig) -> GridMetrics:
        """Derive integer-aligned resolution parameters from a board config.

        The returned ``GridMetrics`` is the single source of truth for all
        pixel dimensions used during texture synthesis.  Tests should call
        this method rather than reimplementing the snapping logic.

        Args:
            config: The board configuration.

        Returns:
            A ``GridMetrics`` tuple with ``square_px``, ``marker_px``,
            ``quiet_zone_px``, and ``effective_px_per_m``.
        """
        if config.type == BoardType.APRILGRID:
            assert config.spacing_ratio is not None
            square_size = config.marker_size * (1.0 + config.spacing_ratio)
        else:
            assert config.square_size is not None
            square_size = config.square_size

        # Snap marker_px UP to the next multiple of the tag grid size so that
        # every data-bit module occupies an identical number of pixels.
        grid_size = TAG_GRID_SIZES.get(config.dictionary, 8)
        marker_px = ceil(config.marker_size * self.px_per_m / grid_size) * grid_size

        effective_px_per_m = marker_px / config.marker_size

        # Integer-align square_px to the nearest EVEN integer so that:
        # 1) r*square_px is always exact integer → grid intersections on pixel
        #    boundaries, eliminating the ≤0.5 px quantization from round().
        # 2) Cell centers at (r+0.5)*square_px are exact half-integers.
        # 3) With even marker_px, tag top-left corners are integer-aligned →
        #    zero-interpolation compositing via direct array slicing.
        square_px = max(2, round(square_size * effective_px_per_m / 2) * 2)

        # Recompute effective resolution from the integer-aligned square so all
        # downstream dimensions are consistent with the snapped grid.
        effective_px_per_m = square_px / square_size

        # Re-snap marker_px under the adjusted resolution (still grid-aligned)
        marker_px = ceil(config.marker_size * effective_px_per_m / grid_size) * grid_size

        quiet_zone_px = round(config.quiet_zone_m * effective_px_per_m)

        return GridMetrics(square_px, marker_px, quiet_zone_px, effective_px_per_m)

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
        gm = self.compute_grid_metrics(config)

        width_px = config.cols * gm.square_px + 2 * gm.quiet_zone_px
        height_px = config.rows * gm.square_px + 2 * gm.quiet_zone_px

        # 3. Initialize Image (White background)
        img = np.full((height_px, width_px), 255, dtype=np.uint8)

        # 4. Draw Board Content
        if config.type == BoardType.CHARUCO:
            self._draw_charuco(img, config, gm.square_px, gm.marker_px, gm.quiet_zone_px)
        elif config.type == BoardType.APRILGRID:
            self._draw_aprilgrid(img, config, gm.square_px, gm.marker_px, gm.quiet_zone_px)

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
        interpolation: int = cv2.INTER_LINEAR,
    ) -> None:
        """Composite a tag onto the canvas at a sub-pixel accurate position.

        When the translation is integer-aligned (the common case with
        integer-snapped grid resolution), the tag is placed via direct array
        slicing — zero interpolation, zero ringing, mathematically perfect
        binary edges.

        For the rare sub-pixel case, an affine warp with bilinear interpolation
        is used. Bilinear (not bicubic) avoids the Gibbs overshoot/undershoot
        that cubic interpolation causes on binary step edges, which would
        displace the effective saddle point for Harris-based sub-pixel refiners.

        The result is composited via element-wise minimum so dark tag pixels
        are never brightened by the white canvas background.

        Args:
            canvas: Target image array (modified in-place).
            tag_img: Tag image to composite (grayscale uint8).
            center_x: Continuous x coordinate of the tag center on the canvas.
            center_y: Continuous y coordinate of the tag center on the canvas.
            interpolation: OpenCV interpolation flag for the affine warp fallback.
        """
        tag_h, tag_w = tag_img.shape[:2]

        # Translation: map tag center to the target canvas position
        tx = center_x - tag_w / 2.0
        ty = center_y - tag_h / 2.0

        # Fast path: integer translation → direct array slicing (zero interpolation)
        tx_r, ty_r = round(tx), round(ty)
        if abs(tx - tx_r) < 1e-6 and abs(ty - ty_r) < 1e-6:
            x0 = max(0, tx_r)
            y0 = max(0, ty_r)
            x1 = min(canvas.shape[1], tx_r + tag_w)
            y1 = min(canvas.shape[0], ty_r + tag_h)
            sx0 = x0 - tx_r
            sy0 = y0 - ty_r
            np.minimum(
                canvas[y0:y1, x0:x1],
                tag_img[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)],
                out=canvas[y0:y1, x0:x1],
            )
            return

        # Sub-pixel fallback: bilinear warp (no cubic to avoid Gibbs ringing)
        M = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty]], dtype=np.float64)

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
        square_px: int,
        marker_px: int,
        quiet_zone_px: int = 0,
    ) -> None:
        """Draw a ChArUco checkerboard pattern.

        Args:
            img: The target image array.
            config: The board configuration.
            square_px: Integer-aligned cell size in pixels.
            marker_px: Marker size in pixels (pre-snapped to grid_size multiple).
            quiet_zone_px: White border width in pixels around the grid.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0
        tag_ids = config.ids

        for r in range(rows):
            for c in range(cols):
                is_white = (r + c) % 2 == 0

                # Cell boundaries are exact integers (no rounding needed)
                y0 = r * square_px + quiet_zone_px
                x0 = c * square_px + quiet_zone_px
                y1 = (r + 1) * square_px + quiet_zone_px
                x1 = (c + 1) * square_px + quiet_zone_px

                if not is_white:
                    img[y0:y1, x0:x1] = 0
                else:
                    current_tag_id = tag_ids[tag_id] if tag_ids is not None else tag_id
                    tag_img = generate_tag_image(
                        family=config.dictionary,
                        tag_id=current_tag_id,
                        size_pixels=marker_px,
                        border_bits=1,
                    )
                    if tag_img is None:
                        raise ValueError(
                            f"Unsupported tag dictionary for board rendering: {config.dictionary}"
                        )
                    center_x = (x0 + x1) / 2.0
                    center_y = (y0 + y1) / 2.0
                    self._composite_tag_subpixel(img, tag_img, center_x, center_y)
                    tag_id += 1

    def _draw_aprilgrid(
        self,
        img: np.ndarray,
        config: BoardConfig,
        square_px: int,
        marker_px: int,
        quiet_zone_px: int = 0,
    ) -> None:
        """Draw an AprilGrid pattern (tags in every cell + corner squares).

        Args:
            img: The target image array.
            config: The board configuration.
            square_px: Integer-aligned cell size in pixels.
            marker_px: Marker size in pixels (pre-snapped to grid_size multiple).
            quiet_zone_px: White border width in pixels around the grid.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0
        tag_ids = config.ids

        for r in range(rows):
            for c in range(cols):
                # Cell boundaries are exact integers (no rounding needed)
                y0 = r * square_px + quiet_zone_px
                x0 = c * square_px + quiet_zone_px
                y1 = (r + 1) * square_px + quiet_zone_px
                x1 = (c + 1) * square_px + quiet_zone_px

                current_tag_id = tag_ids[tag_id] if tag_ids is not None else tag_id
                tag_img = generate_tag_image(
                    family=config.dictionary,
                    tag_id=current_tag_id,
                    size_pixels=marker_px,
                    border_bits=1,
                )
                if tag_img is None:
                    raise ValueError(
                        f"Unsupported tag dictionary for board rendering: {config.dictionary}"
                    )
                center_x = (x0 + x1) / 2.0
                center_y = (y0 + y1) / 2.0
                self._composite_tag_subpixel(img, tag_img, center_x, center_y)
                tag_id += 1

        # Draw black corner squares at grid intersections.
        # corner_px is forced to an even integer so that integer offsets from
        # the center are symmetric on both sides.
        corner_ratio = config.kalibr_corner_ratio if config.kalibr_corner_ratio is not None else 0.1
        corner_px = max(2, int(marker_px * corner_ratio) & ~1)
        corner_half = corner_px // 2
        for r in range(rows + 1):
            for c in range(cols + 1):
                cy = r * square_px + quiet_zone_px
                cx = c * square_px + quiet_zone_px
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
