from __future__ import annotations

from typing import TYPE_CHECKING

from render_tag.core.schema.subject import BoardSubjectConfig, TagSubjectConfig

from .board import BoardStrategy
from .occluder import OccluderStrategy
from .tags import TagStrategy

if TYPE_CHECKING:
    from render_tag.core.schema.subject import OccluderConfig, SubjectConfig

    from .base import SubjectStrategy


def get_subject_strategy(config: SubjectConfig) -> SubjectStrategy:
    """Factory to return the appropriate strategy based on subject type.

    Args:
        config: The polymorphic subject configuration.

    Returns:
        An initialized SubjectStrategy implementation.

    Raises:
        ValueError: If the subject type is unknown.
    """
    # config is a RootModel, we need to check the type of config.root
    actual_config = getattr(config, "root", config)

    if isinstance(actual_config, TagSubjectConfig):
        return TagStrategy(actual_config)
    elif isinstance(actual_config, BoardSubjectConfig):
        return BoardStrategy(actual_config)

    raise ValueError(f"Unknown subject type: {type(actual_config)}")


def get_occluder_strategy(config: OccluderConfig | None) -> OccluderStrategy | None:
    """Return an OccluderStrategy if occluders are configured, else None."""
    if config is None or not config.enabled:
        return None
    return OccluderStrategy(config)
