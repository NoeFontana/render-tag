
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from ..core.schema.board import BoardConfig, BoardType
from .tags import generate_tag_image


class TextureFactory:
    """Bit-perfect calibration target texture synthesizer."""

    def __init__(self, px_per_mm: float = 10.0, cache_dir: Path | None = None):
        """
        Args:
            px_per_mm: Resolution of the generated texture (default: 10px/mm)
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
                return cv2.imread(str(cache_path), cv2.IMREAD_GRAYSCALE)

        # 2. Calculate Dimensions
        if config.type == BoardType.APRILGRID:
            # AprilGrid: square_size = marker_size * (1 + spacing_ratio)
            square_size = config.marker_size * (1.0 + config.spacing_ratio)
        else:
            # ChArUco: square_size is explicit
            square_size = config.square_size

        width_m = config.cols * square_size
        height_m = config.rows * square_size

        width_px = round(width_m * self.px_per_m)
        height_px = round(height_m * self.px_per_m)
        square_px = round(square_size * self.px_per_m)
        marker_px = round(config.marker_size * self.px_per_m)

        # 3. Initialize Image (White background)
        img = np.full((height_px, width_px), 255, dtype=np.uint8)

        # 4. Draw Board Content
        if config.type == BoardType.CHARUCO:
            self._draw_charuco(img, config, square_px, marker_px)
        elif config.type == BoardType.APRILGRID:
            self._draw_aprilgrid(img, config, square_px, marker_px)

        # 5. Save to Cache
        if cache_path:
            cv2.imwrite(str(cache_path), img)

        return img

    def _draw_charuco(self, img: np.ndarray, config: BoardConfig, square_px: int, marker_px: int):
        """Draw a ChArUco checkerboard pattern.
        
        Args:
            img: The target image array.
            config: The board configuration.
            square_px: Size of each cell in pixels.
            marker_px: Size of each tag in pixels.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0

        for r in range(rows):
            for c in range(cols):
                # Checkerboard pattern
                # OpenCV ChArUco: (0,0) is white. (r+c) % 2 == 0 is white.
                is_white = (r + c) % 2 == 0
                
                y0, x0 = r * square_px, c * square_px
                # Handle potential rounding drift at the edges
                y1 = (r + 1) * square_px if r < rows - 1 else img.shape[0]
                x1 = (c + 1) * square_px if c < cols - 1 else img.shape[1]

                if not is_white:
                    # Draw black square
                    img[y0:y1, x0:x1] = 0
                else:
                    # Draw marker in white square
                    tag_img = generate_tag_image(
                        family=config.dictionary,
                        tag_id=tag_id,
                        size_pixels=marker_px,
                        border_bits=1,
                    )
                    if tag_img is not None:
                        # Center tag in square
                        dy = (y1 - y0 - marker_px) // 2
                        dx = (x1 - x0 - marker_px) // 2
                        img[y0 + dy : y0 + dy + marker_px, x0 + dx : x0 + dx + marker_px] = tag_img
                    tag_id += 1

    def _draw_aprilgrid(self, img: np.ndarray, config: BoardConfig, square_px: int, marker_px: int):
        """Draw an AprilGrid pattern (tags in every cell + corner squares).
        
        Args:
            img: The target image array.
            config: The board configuration.
            square_px: Size of each cell in pixels.
            marker_px: Size of each tag in pixels.
        """
        rows, cols = config.rows, config.cols
        tag_id = 0
        
        # AprilGrid: 1 bit border, 1 bit white margin by default in Kalibr?
        # Specification says: tags in every cell.
        
        for r in range(rows):
            for c in range(cols):
                y0, x0 = r * square_px, c * square_px
                y1 = (r + 1) * square_px if r < rows - 1 else img.shape[0]
                x1 = (c + 1) * square_px if c < cols - 1 else img.shape[1]

                # Draw tag
                tag_img = generate_tag_image(
                    family=config.dictionary,
                    tag_id=tag_id,
                    size_pixels=marker_px,
                    border_bits=1,
                )
                if tag_img is not None:
                    dy = (y1 - y0 - marker_px) // 2
                    dx = (x1 - x0 - marker_px) // 2
                    img[y0 + dy : y0 + dy + marker_px, x0 + dx : x0 + dx + marker_px] = tag_img
                tag_id += 1

        # Draw black corner squares (AprilGrid characteristic)
        # These are at the intersections of the grid
        corner_px = round(marker_px * 0.1) # Small fixed ratio for now or parametric?
        # Specification says "Small black corner squares". 
        # Usually they are quite small, e.g. 2-5% of marker size.
        
        for r in range(rows + 1):
            for c in range(cols + 1):
                y = r * square_px
                x = c * square_px
                
                cy0 = max(0, y - corner_px // 2)
                cy1 = min(img.shape[0], y + (corner_px + 1) // 2)
                cx0 = max(0, x - corner_px // 2)
                cx1 = min(img.shape[1], x + (corner_px + 1) // 2)
                
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
