import logging
import os
import sys
from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import orjson

# Standard LogRecord attributes to ignore when extracting context
RESERVED_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
    "payload",  # We handle payload explicitly
}


def _json_default(obj: Any) -> Any:
    """Default serializer for orjson to handle complex types."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, (set, tuple)):
        return list(obj)

    # Handle Blender mathutils if present
    type_name = type(obj).__name__
    if type_name in ["Vector", "Matrix", "Euler", "Quaternion", "Color"]:
        if hasattr(obj, "to_list"):
            return obj.to_list()
        return list(obj)

    try:
        return str(obj)
    except Exception:
        return f"<{type(obj).__name__}>"


# Standard logging kwargs that should be passed through to the underlying logger
LOGGING_ARGS = {"exc_info", "stack_info", "stacklevel", "extra"}


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that binds context variables to all log entries."""

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None):
        super().__init__(logger, extra or {})

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        # Separate logging kwargs from context kwargs
        context = {}
        logging_kwargs = {}

        for k, v in kwargs.items():
            if k in LOGGING_ARGS:
                logging_kwargs[k] = v
            else:
                context[k] = v

        # Start with adapter's bound context
        merged_context = dict(self.extra) if self.extra else {}

        # Merge call-site context
        merged_context.update(context)

        # Handle 'extra' specifically if it was passed
        if "extra" in logging_kwargs:
            merged_context.update(logging_kwargs["extra"])

        logging_kwargs["extra"] = merged_context
        return msg, logging_kwargs

    def bind(self, **kwargs: Any) -> "ContextLogger":
        """Return a new ContextLogger with the added context."""
        new_context = dict(self.extra) if self.extra else {}
        new_context.update(kwargs)
        return ContextLogger(self.logger, new_context)


class JSONFormatter(logging.Formatter):
    """NDJSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract context
        context = {
            k: v
            for k, v in record.__dict__.items()
            if k not in RESERVED_ATTRS and not k.startswith("_")
        }

        # Extract payload if passed (legacy support or explicit payload)
        payload = getattr(record, "payload", {})
        if not isinstance(payload, dict):
            payload = {"data": payload}

        event = context.pop("event", None)

        # Create structured log
        log_data = {
            "type": "log",
            "level": record.levelname,
            "logger": record.name,
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "message": record.getMessage(),
            "context": context,
            "payload": payload,
        }
        if event:
            log_data["event"] = event

        # Determine log type
        if hasattr(record, "log_type"):
            log_data["type"] = record.log_type
        elif record.levelno >= logging.ERROR:
            log_data["type"] = "error"

        # Serialize with orjson
        return orjson.dumps(
            log_data,
            default=_json_default,
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME,
        ).decode("utf-8")


def setup_logging(level: int = logging.INFO):
    """Sets up standard logging configuration for the project.

    Respects LOG_FORMAT environment variable ('rich' or 'json').
    """
    log_format = os.environ.get("LOG_FORMAT", "rich").lower()
    root = logging.getLogger()

    # We set strict level on root, but handlers can have their own
    root.setLevel(level)

    # Clear existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    if log_format == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)
    else:
        # Use RichHandler for pretty printing
        try:
            from rich.console import Console
            from rich.logging import RichHandler
            from rich.theme import Theme

            # Custom theme for better visibility
            theme = Theme(
                {
                    "logging.level.info": "green",
                    "logging.level.warning": "yellow",
                    "logging.level.error": "bold red",
                    "logging.keyword": "bold blue",
                }
            )

            console = Console(theme=theme, stderr=True)

            handler = RichHandler(
                console=console,
                rich_tracebacks=True,
                markup=True,
                show_path=False,
                omit_repeated_times=False,
            )
            # RichHandler formats message itself, we just need basic format if anything
            # But normally it doesn't need a formatter
            root.addHandler(handler)
        except ImportError:
            # Fallback to standard logging if rich is missing (unlikely given dependencies)
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            root.addHandler(handler)


def get_logger(name: str) -> ContextLogger:
    """Gets a logger instance for a given name wrapped in ContextLogger."""
    return ContextLogger(logging.getLogger(name))
