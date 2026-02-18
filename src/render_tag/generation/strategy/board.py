
from __future__ import annotations
from typing import TYPE_CHECKING
from .base import SubjectStrategy

if TYPE_CHECKING:
    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.schema.recipe import ObjectRecipe
    from render_tag.core.schema.subject import BoardSubjectConfig

class BoardStrategy(SubjectStrategy):
    """Strategy for generating a single rigid calibration board."""

    def __init__(self, config: BoardSubjectConfig):
        self.config = config

    def prepare_assets(self, context: GenerationContext) -> None:
        pass

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        return []
