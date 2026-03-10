"""
Board Strategy implementation for rigid calibration targets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from render_tag.core.schema.board import BoardConfig, BoardType
from render_tag.core.schema.recipe import ObjectRecipe
from render_tag.generation.texture_factory import TextureFactory

from .base import SubjectStrategy

if TYPE_CHECKING:
    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.schema.subject import BoardSubjectConfig


class BoardStrategy(SubjectStrategy):
    """Strategy for generating a single high-fidelity calibration board.

    This strategy utilizes the TextureFactory to synthesize bit-perfect textures
    for ChArUco and AprilGrid targets. It ensures that the 3D model in the
    renderer exactly matches the physical dimensions specified in the config.
    """

    def __init__(self, config: BoardSubjectConfig):
        """Initialize the strategy.

        Args:
            config: Configuration for the board subject domain.
        """
        self.config = config
        self._board_config = self._map_to_board_config(config)
        self._texture_path: str | None = None

    def _map_to_board_config(self, config: BoardSubjectConfig) -> BoardConfig:
        """Map the SubjectConfig to the standard BoardConfig used by the factory.

        Args:
            config: The source subject configuration.

        Returns:
            A BoardConfig instance compatible with the texture synthesizer.
        """
        return BoardConfig(
            type=BoardType.APRILGRID if config.spacing_ratio is not None else BoardType.CHARUCO,
            rows=config.rows,
            cols=config.cols,
            marker_size=config.marker_size_mm / 1000.0,
            dictionary=config.dictionary,
            spacing_ratio=config.spacing_ratio,
            square_size=config.square_size_mm / 1000.0 if config.square_size_mm else None,
            ids=config.ids,
        )

    def prepare_assets(self, context: GenerationContext) -> None:
        """Generate and cache the high-resolution board texture.

        Args:
            context: The shared generation context.
        """
        cache_dir = context.output_dir / "cache" / "boards" if context.output_dir else None
        factory = TextureFactory(cache_dir=cache_dir)

        # Synthesis happens once per unique configuration using SHA256 caching
        factory.generate_board_texture(self._board_config)

        if cache_dir:
            config_hash = factory._calculate_hash(self._board_config)
            self._texture_path = str((cache_dir / f"board_{config_hash}.png").absolute())

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        """Return a single rigidly-transformed BOARD object.

        Args:
            seed: Scene-specific random seed.
            context: Shared generation context.

        Returns:
            A list containing exactly one ObjectRecipe for the board plane.
        """
        # Calculate physical dimensions from grid parameters
        marker_size = self.config.marker_size_mm / 1000.0
        if self.config.spacing_ratio is not None:
            # AprilGrid: square_size = marker_size * (1 + spacing_ratio)
            square_size = marker_size * (1.0 + self.config.spacing_ratio)
        else:
            # ChArUco: square_size is explicit
            square_size = (
                self.config.square_size_mm / 1000.0 if self.config.square_size_mm else marker_size
            )

        width_m = self.config.cols * square_size
        height_m = self.config.rows * square_size

        # Generate 3D Keypoints for sub-pixel ground truth
        from render_tag.generation.board import (
            BoardSpec,
            compute_aprilgrid_layout,
            compute_charuco_layout,
        )
        from render_tag.generation.board import (
            BoardType as GenBoardType,
        )

        if self.config.spacing_ratio is not None:
            spec = BoardSpec(
                rows=self.config.rows,
                cols=self.config.cols,
                square_size=square_size,
                marker_margin=(square_size - marker_size) / 2.0,
                board_type=GenBoardType.APRILGRID,
            )
            layout = compute_aprilgrid_layout(spec, tag_ids=self._board_config.ids)
        else:
            spec = BoardSpec(
                rows=self.config.rows,
                cols=self.config.cols,
                square_size=square_size,
                marker_margin=(square_size - marker_size) / 2.0,
                board_type=GenBoardType.CHARUCO,
            )
            layout = compute_charuco_layout(spec, tag_ids=self._board_config.ids)

        keypoints_3d = []
        # 1. Tag corners (standardized order)
        # Normalize keypoints so that they are in the range [-1, 1] relative to the 2x2 base mesh.
        # The object's transform_matrix will scale them back to physical meters.
        for pos in layout.tag_positions:
            nx = pos.x / (width_m / 2.0)
            ny = pos.y / (height_m / 2.0)
            nmx = (marker_size / 2.0) / (width_m / 2.0)
            nmy = (marker_size / 2.0) / (height_m / 2.0)
            keypoints_3d.extend(
                [
                    [nx - nmx, ny + nmy, 0.0],
                    [nx + nmx, ny + nmy, 0.0],
                    [nx + nmx, ny - nmy, 0.0],
                    [nx - nmx, ny - nmy, 0.0],
                ]
            )

        calibration_points_3d = []
        # 2. Calibration points (saddle points)
        for pos in layout.calibration_positions:
            nx = pos.x / (width_m / 2.0)
            ny = pos.y / (height_m / 2.0)
            calibration_points_3d.append([nx, ny, 0.0])

        # Apply a small random offset to the board to avoid centering bias
        import numpy as np

        from render_tag.core.seeding import derive_seed

        rng = np.random.default_rng(derive_seed(seed, "layout_offset", 0))
        offset_radius = context.gen_config.physics.scatter_radius * 0.5
        location = [
            rng.uniform(-offset_radius, offset_radius),
            rng.uniform(-offset_radius, offset_radius),
            0.0,
        ]

        return [
            ObjectRecipe(
                type="BOARD",
                name="CalibrationBoard",
                location=location,
                rotation_euler=[0, 0, 0],
                scale=[width_m, height_m, 1.0],  # Map unit plane to physical meters
                texture_path=self._texture_path,
                board=self._board_config,
                keypoints_3d=keypoints_3d,
                calibration_points_3d=calibration_points_3d if calibration_points_3d else None,
            )
        ]
