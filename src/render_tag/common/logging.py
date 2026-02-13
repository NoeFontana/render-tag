import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import orjson
from pydantic import BaseModel, Field


class LogSchema(BaseModel):
    """Structured log schema for JSON IPC."""
    type: str = "log"
    level: str
    logger: str
    timestamp: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


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
    
    # Handle Blender mathutils if present
    # We check by name to avoid direct dependency in common
    type_name = type(obj).__name__
    if type_name in ["Vector", "Matrix", "Euler", "Quaternion", "Color"]:
        if hasattr(obj, "to_list"):
            return obj.to_list()
        # Fallback for Matrix which has __iter__ but maybe not to_list in some contexts
        return list(obj)
        
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class JSONFormatter(logging.Formatter):
    """NDJSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract payload if passed in extra
        payload = getattr(record, "payload", {})
        if not isinstance(payload, dict):
            payload = {"data": payload}

        # Create structured log
        log_entry = LogSchema(
            level=record.levelname,
            logger=record.name,
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            message=record.getMessage(),
            payload=payload
        )
        
        # Determine log type
        if hasattr(record, "log_type"):
            log_entry.type = record.log_type
        elif record.levelno >= logging.ERROR:
            log_entry.type = "error"

        # Serialize with orjson
        return orjson.dumps(
            log_entry.model_dump(),
            default=_json_default,
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME
        ).decode("utf-8")


def setup_logging(level: int = logging.INFO):
    """Sets up standard logging configuration for the project."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Gets a logger instance for a given name."""
    return logging.getLogger(name)
