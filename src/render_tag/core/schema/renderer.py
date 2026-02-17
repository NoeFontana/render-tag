"""
Schema for rendering engine configuration.
"""

from typing import Literal
from pydantic import BaseModel, Field

class RendererConfig(BaseModel):
    """Configuration for the rendering engine."""

    mode: Literal["cycles", "eevee", "workbench"] = "cycles"
    samples: int = Field(default=128, ge=1)
    denoising: bool = True
    
    # CV-Safe parameters
    noise_threshold: float = Field(default=0.05, ge=0.0)
    max_samples: int = Field(default=128, ge=1)
    enable_denoising: bool = True
    denoiser_type: str = "INTEL"
