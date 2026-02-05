"""
ZeroMQ Protocol Schemas for Hot Loop Optimization.
"""

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CommandType(str, Enum):
    """Types of commands that can be sent to the Backend."""
    INIT = "INIT"       # Pre-load heavy assets
    RENDER = "RENDER"   # Execute a scene recipe
    RESET = "RESET"     # Partial reset of volatile state
    STATUS = "STATUS"   # Heartbeat and telemetry request
    SHUTDOWN = "SHUTDOWN"


class Command(BaseModel):
    """A command sent from Host to Backend."""
    command_type: CommandType
    payload: Optional[Dict[str, Any]] = None
    request_id: str = Field(description="Unique ID for tracking the request/response pair")


class ResponseStatus(str, Enum):
    """Status of a command execution."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class Response(BaseModel):
    """A response sent from Backend to Host."""
    status: ResponseStatus
    request_id: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class Telemetry(BaseModel):
    """Telemetry data reported by the Backend."""
    vram_used_mb: float
    vram_total_mb: float
    cpu_usage_percent: float
    state_hash: str
    uptime_seconds: float


def calculate_state_hash(assets: List[str], parameters: Dict[str, Any]) -> str:
    """
    Calculates a deterministic hash representing the current resident state of the backend.
    
    Includes loaded assets (HDRIs, textures) and semi-persistent parameters.
    """
    state_data = {
        "assets": sorted(assets),
        "parameters": parameters
    }
    state_json = json.dumps(state_data, sort_keys=True)
    return hashlib.sha256(state_json.encode()).hexdigest()
