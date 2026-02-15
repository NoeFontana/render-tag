"""
Advanced resource management utilities for render-tag.

Provides patterns for robust resource acquisition, composite lifecycles,
and guaranteed cleanup using ExitStack.
"""

import contextlib
import logging
from collections.abc import Generator
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ManagedResource(Protocol):
    """Protocol for resources that manage their own lifecycle."""

    def start(self) -> None:
        """Initialize and start the resource."""
        ...

    def stop(self) -> None:
        """Gracefully shut down and cleanup the resource."""
        ...


class ResourceStack:
    """
    A Staff Engineer level wrapper around contextlib.ExitStack.
    Manages a collection of resources and ensures they are cleaned up in reverse order.
    """

    def __init__(self):
        self._stack = contextlib.ExitStack()
        self._active = False

    def enter_context(self, cm: Any) -> Any:
        """Add a context manager to the stack."""
        if isinstance(cm, ResourceStack):
            # If we are entering another ResourceStack, we want to merge its inner stack
            return self._stack.enter_context(cm._stack)
        return self._stack.enter_context(cm)

    def push_resource(self, resource: ManagedResource):
        """
        Adds a ManagedResource to the stack.
        Ensures that 'stop' is called during cleanup.
        """

        def _cleanup():
            try:
                resource.stop()
            except Exception as e:
                logger.error(f"Error during resource cleanup: {e}")

        self._stack.callback(_cleanup)

    def __enter__(self):
        self._active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._active = False
        return self._stack.__exit__(exc_type, exc_val, exc_tb)

    def close(self):
        """Explicitly close the stack."""
        self._stack.close()
        self._active = False

    def pop_all(self) -> "ResourceStack":
        """
        Preserve all registered resources by moving them to a new ResourceStack.
        Useful for handovers between short-lived and long-lived scopes.
        """
        new_stack = ResourceStack()
        new_stack._stack = self._stack.pop_all()
        new_stack._active = True
        return new_stack


@contextlib.contextmanager
def safe_resource_pool() -> Generator[ResourceStack, None, None]:
    """
    Provides a ResourceStack that automatically cleans up all registered
    resources on exit, even if an exception occurs during acquisition.
    """
    with ResourceStack() as stack:
        yield stack
