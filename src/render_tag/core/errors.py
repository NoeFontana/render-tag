"""
Centralized exception hierarchy for render-tag.

This module defines the domain-specific errors used throughout the application,
allowing for granular error handling and semantic reporting.
"""


class RenderTagError(Exception):
    """Base class for all render-tag exceptions."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class ConfigurationError(RenderTagError):
    """Raised when configuration loading or validation fails."""


class OrchestrationError(RenderTagError):
    """Base class for errors occurring during the orchestration phase."""


class WorkerStartupError(OrchestrationError):
    """Raised when a worker process fails to start or become healthy."""


class WorkerCommunicationError(OrchestrationError):
    """Raised when ZMQ communication with a worker fails (timeout, disconnect)."""


class RenderError(RenderTagError):
    """Raised when a render job fails within the Blender backend."""


class AssetError(RenderTagError):
    """Raised when asset validation or loading fails."""
