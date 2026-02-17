"""
Advanced resource management utilities for render-tag.

Provides patterns for robust resource acquisition, composite lifecycles,
and guaranteed cleanup using ExitStack.
"""

import contextlib
import os
from collections.abc import Generator
from typing import Any, Protocol, runtime_checkable

from render_tag.core.logging import get_logger

logger = get_logger(__name__)


def get_thread_budget(num_workers: int = 1, system_reserve: int = 2) -> int:
    """
    Calculate the optimal number of threads per worker based on hardware.
    Shifts the burden from user config to runtime calculation.

    Args:
        num_workers: Number of active workers.
        system_reserve: Number of cores to leave for the OS and Orchestrator.

    Returns:
        Number of threads per worker (minimum 1).
    """
    total_cores = os.cpu_count() or 1
    safe_cores = max(1, total_cores - system_reserve)
    budget = max(1, safe_cores // num_workers)

    logger.info(
        "Auto-Throttling Threads",
        cores=total_cores,
        reserved=system_reserve,
        budget=budget,
    )
    return budget


def calculate_worker_memory_budget(
    num_workers: int = 1,
    explicit_limit_mb: int | None = None,
    safety_factor: float = 0.75,
    min_limit_mb: int = 512,
) -> int:
    """
    Calculate the memory budget per worker in MB.

    Args:
        num_workers: Number of workers in the pool.
        explicit_limit_mb: Hard limit if provided by user.
        safety_factor: Percent of system RAM to allocate to workers (0.0 to 1.0).
        min_limit_mb: Sane floor for worker memory.

    Returns:
        Calculated limit in MB.
    """
    if explicit_limit_mb is not None:
        return explicit_limit_mb

    try:
        import psutil

        total_ram_bytes = psutil.virtual_memory().total
        total_ram_mb = total_ram_bytes / (1024 * 1024)

        # Apply safety factor and divide by workers
        available_mb = total_ram_mb * safety_factor
        budget_per_worker = int(available_mb // num_workers)

        final_budget = max(budget_per_worker, min_limit_mb)

        logger.info(
            "Auto-Tuning Memory",
            total_system_ram_mb=int(total_ram_mb),
            workers=num_workers,
            budget_per_worker_mb=final_budget,
        )
        return final_budget

    except ImportError:
        logger.warning("psutil not installed. Memory auto-tuning disabled. Using default limit.")
        return 4096  # Sane fallback if psutil is missing


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
                logger.error("Error during resource cleanup", error=str(e))

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
