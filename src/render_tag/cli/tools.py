"""
Shared CLI utilities.
"""

import json
import os
import shutil
from pathlib import Path

from rich.console import Console

from render_tag.core.config import GenConfig
from render_tag.orchestration.assets import AssetManager

console = Console()


def get_asset_manager() -> AssetManager:
    """Helper to initialize AssetManager with local directory."""
    # Assets folder is at the root of the project by default
    # but can be overridden by environment variable
    # We assume this code is in src/render_tag/cli_pkg/tools.py
    # So parents[3] gets to project root
    default_dir = Path(__file__).resolve().parents[3] / "assets"
    local_dir = Path(os.environ.get("RENDER_TAG_ASSETS_DIR", default_dir))
    return AssetManager(local_dir=local_dir)


def check_blenderproc_installed() -> bool:
    """Check if blenderproc is available in the system."""
    return shutil.which("blenderproc") is not None


def check_audit_installed() -> bool:
    """Check if auditing dependencies (polars, plotly) are installed."""
    try:
        import plotly.graph_objects as _  # noqa: F401
        import polars as _polars  # noqa: F401

        return True
    except ImportError:
        return False


def check_viz_installed() -> bool:
    """Check if visualization dependencies (matplotlib) are installed."""
    try:
        import matplotlib.pyplot as _  # noqa: F401

        return True
    except ImportError:
        return False


def check_orchestration_installed() -> bool:
    """Check if orchestration dependencies (pyzmq) are installed."""
    try:
        import zmq as _  # noqa: F401

        return True
    except ImportError:
        return False


def check_hub_installed() -> bool:
    """Check if Hub management dependencies (datasets, huggingface_hub) are installed."""
    try:
        import datasets as _ds  # noqa: F401
        import huggingface_hub as _hf  # noqa: F401

        return True
    except ImportError:
        return False


def check_assets_installed() -> bool:
    """Check if asset sync dependencies (huggingface_hub) are installed."""
    try:
        import huggingface_hub as _  # noqa: F401

        return True
    except ImportError:
        return False


def serialize_config_to_json(config: GenConfig, output_path: Path) -> None:
    """Serialize the validated config to JSON for the Blender subprocess.

    Args:
        config: Validated GenConfig instance
        output_path: Path to write the JSON file
    """
    # Convert Pydantic model to dict, handling Path objects
    config_dict = config.model_dump(mode="json")

    with open(output_path, "w") as f:
        json.dump(config_dict, f, indent=2, default=str)
