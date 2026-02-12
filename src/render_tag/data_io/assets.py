"""
Asset provider for on-demand downloading of assets from Hugging Face.
"""

import logging
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    hf_hub_download = None

logger = logging.getLogger(__name__)

class AssetProvider:
    """Provides access to assets, downloading them from Hugging Face if missing locally."""

    def __init__(self, local_dir: Path | str = "assets", repo_id: str = "NoeFontana/render-tag-assets"):
        self.local_dir = Path(local_dir).absolute()
        self.repo_id = repo_id

    def resolve_path(self, asset_path: str) -> Path:
        """
        Resolves a path to an asset. If it's a relative path and doesn't exist locally,
        it attempts to download it from the Hugging Face dataset.

        Args:
            asset_path: Path to the asset (relative to assets/ or absolute).

        Returns:
            Path: The absolute path to the local file.
        """
        p = Path(asset_path)
        
        # 1. Absolute path check
        if p.is_absolute():
            return p

        # 2. Local check
        local_p = self.local_dir / p
        if local_p.exists():
            return local_p

        # 3. Remote download
        if hf_hub_download is None:
            logger.error("huggingface_hub not installed, cannot download missing asset: %s", asset_path)
            return local_p

        logger.info("Asset %s not found locally. Attempting download from %s", asset_path, self.repo_id)
        try:
            downloaded_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=str(p),
                local_dir=str(self.local_dir),
                repo_type="dataset"
            )
            return Path(downloaded_path)
        except Exception as e:
            logger.error("Failed to download asset %s from HF: %s", asset_path, e)
            # Return the local path anyway, it will probably fail later but we tried
            return local_p
