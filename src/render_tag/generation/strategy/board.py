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
    """Strategy for generating a single rigid calibration board."""

    def __init__(self, config: BoardSubjectConfig):
        self.config = config
        self._board_config = self._map_to_board_config(config)
        self._texture_path: str | None = None

    def _map_to_board_config(self, config: BoardSubjectConfig) -> BoardConfig:
        """Map the SubjectConfig to the standard BoardConfig used by the factory."""
        return BoardConfig(
            type=BoardType.APRILGRID if config.spacing_ratio is not None else BoardType.CHARUCO,
            rows=config.rows,
            cols=config.cols,
            marker_size=config.marker_size,
            dictionary=config.dictionary,
            spacing_ratio=config.spacing_ratio,
            square_size=config.square_size,
        )

    def prepare_assets(self, context: GenerationContext) -> None:
        """Generate and cache the board texture."""
        cache_dir = context.output_dir / "cache" / "boards" if context.output_dir else None
        factory = TextureFactory(cache_dir=cache_dir)
        
        # This will generate the texture and save it to cache
        factory.generate_board_texture(self._board_config)
        
        if cache_dir:
            config_hash = factory._calculate_hash(self._board_config)
            self._texture_path = str((cache_dir / f"board_{config_hash}.png").absolute())

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        """Return a single scaled BOARD object."""
        # Calculate physical dimensions
        if self.config.spacing_ratio is not None:
            # AprilGrid: square_size = marker_size * (1 + spacing_ratio)
            square_size = self.config.marker_size * (1.0 + self.config.spacing_ratio)
        else:
            square_size = self.config.square_size

        width_m = self.config.cols * square_size
        height_m = self.config.rows * square_size

        # 3D Keypoints for the board
        # We reuse the logic from compiler.py for now
        from render_tag.generation.board import BoardSpec, BoardType as GenBoardType, compute_aprilgrid_layout, compute_charuco_layout
        
        if self.config.spacing_ratio is not None:
            spec = BoardSpec(
                rows=self.config.rows,
                cols=self.config.cols,
                square_size=square_size,
                marker_margin=(square_size - self.config.marker_size) / 2.0,
                board_type=GenBoardType.APRILGRID,
            )
            layout = compute_aprilgrid_layout(spec)
        else:
            spec = BoardSpec(
                rows=self.config.rows,
                cols=self.config.cols,
                square_size=self.config.square_size,
                marker_margin=(self.config.square_size - self.config.marker_size) / 2.0,
                board_type=GenBoardType.CHARUCO,
            )
            layout = compute_charuco_layout(spec)

        keypoints_3d = []
        # 1. Tag corners
        m = self.config.marker_size / 2.0
        for pos in layout.tag_positions:
            keypoints_3d.extend([
                [pos.x - m, pos.y + m, 0.0],
                [pos.x + m, pos.y + m, 0.0],
                [pos.x + m, pos.y - m, 0.0],
                [pos.x - m, pos.y - m, 0.0],
            ])
        # 2. Saddle points / Grid intersections
        for pos in layout.corner_positions:
            keypoints_3d.append([pos.x, pos.y, pos.z])

        return [
            ObjectRecipe(
                type="BOARD",
                name="CalibrationBoard",
                location=[0, 0, 0],
                rotation_euler=[0, 0, 0],
                scale=[width_m, height_m, 1.0], # Physical scaling of unit plane
                texture_path=self._texture_path,
                board=self._board_config,
                keypoints_3d=keypoints_3d,
            )
        ]
