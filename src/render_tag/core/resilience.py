"""
Resilience patterns and utilities for render-tag.

Provides decorators and helpers for retrying operations with backoff, jitter,
and fault tolerance.
"""

import functools
import random
import time
from collections.abc import Callable
from typing import TypeVar

from render_tag.core.errors import RenderTagError
from render_tag.core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


def retry_with_backoff(
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function call with exponential backoff.

    Args:
        retries: Maximum number of retries (not including first attempt).
        initial_delay: Delay in seconds before the first retry.
        backoff_factor: Multiplier applied to delay after each failure.
        jitter: If True, adds random jitter to the delay to prevent thundering herds.
        exceptions: Tuple of exceptions to catch and retry on.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logger.error(
                            "Operation failed after retries",
                            operation=func.__name__,
                            attempts=retries + 1,
                            error=str(e),
                        )
                        raise

                    # Calculate delay
                    sleep_time = delay
                    if jitter:
                        sleep_time *= random.uniform(0.5, 1.5)

                    logger.warning(
                        "Operation failed, retrying",
                        operation=func.__name__,
                        attempt=attempt + 1,
                        max_retries=retries,
                        retry_delay=f"{sleep_time:.2f}s",
                        error=str(e),
                    )

                    time.sleep(sleep_time)
                    delay *= backoff_factor

            # Should be unreachable due to raise inside loop
            if last_exception:
                raise last_exception
            raise RenderTagError("Unknown retry error")

        return wrapper

    return decorator
