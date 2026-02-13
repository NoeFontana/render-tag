"""
Mock entry point for blenderproc to satisfy import checks in zmq_server.py
when running integration tests in mock mode.
"""

from tests.mocks.blenderproc_api import (
    clean_up,
    init,
    renderer,
    types,
    world,
)
from tests.mocks.blenderproc_api import (
    object as bproc_object,
)

object = bproc_object

__all__ = ["clean_up", "init", "object", "renderer", "types", "world"]
