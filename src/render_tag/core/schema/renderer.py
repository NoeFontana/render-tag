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

    # Light Path parameters (CV-Safe)
    total_bounces: int = Field(default=4, ge=0)
    diffuse_bounces: int = Field(default=2, ge=0)
    glossy_bounces: int = Field(default=4, ge=0)
    transmission_bounces: int = Field(default=0, ge=0)
    transparent_bounces: int = Field(default=4, ge=0)
    enable_caustics: bool = False
