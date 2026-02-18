
from __future__ import annotations
from typing import TYPE_CHECKING
from .base import SubjectStrategy

if TYPE_CHECKING:
    from render_tag.cli.pipeline import GenerationContext
    from render_tag.core.schema.recipe import ObjectRecipe
    from render_tag.core.schema.subject import TagSubjectConfig

class TagStrategy(SubjectStrategy):
    """Strategy for scattering individual tags in a scene."""

    def __init__(self, config: TagSubjectConfig):
        self.config = config

    def prepare_assets(self, context: GenerationContext) -> None:
        pass

    def sample_pose(self, seed: int, context: GenerationContext) -> list[ObjectRecipe]:
        return []
