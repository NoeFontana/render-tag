"""
Asset provider for on-demand downloading of assets from Hugging Face.
"""

import logging
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

logger = logging.getLogger(__name__)


class AssetProvider:
    """Provides access to assets, downloading them from Hugging Face if missing locally."""

    def __init__(
        self, local_dir: Path | str = "assets", repo_id: str = "NoeFontana/render-tag-assets"
    ):
        self.local_dir = Path(local_dir).absolute()
        self.repo_id = repo_id
        self._cache: dict[str, Path] = {}

    def resolve_path(self, asset_path: str) -> Path:
        """
        Resolves a path to an asset. If it's a relative path and doesn't exist locally,
        it attempts to download it from the Hugging Face dataset.

        Args:
            asset_path: Path to the asset (relative to assets/ or absolute).

        Returns:
            Path: The absolute path to the local file.
        """
        if asset_path in self._cache:
            return self._cache[asset_path]

        p = Path(asset_path)

        # 1. Absolute path check
        if p.is_absolute():
            return p

        # 2. Local check
        local_p = self.local_dir / p
        if p.parts and p.parts[0] == self.local_dir.name:
            local_p = self.local_dir.parent / p

        # Robust check: exact match OR prefix match for collections
        exists = local_p.exists()
        if not exists and not p.suffix:
            # Check if any file starts with this prefix in the parent directory
            pattern = f"{local_p.name}*"
            try:
                if any(local_p.parent.glob(pattern)):
                    exists = True
            except Exception:
                pass

        if exists:
            self._cache[asset_path] = local_p
            return local_p

        # 3. Remote download
        logger.info(
            "Asset %s not found locally. Attempting download from %s", asset_path, self.repo_id
        )
        try:
            # Strip the assets/ prefix if it exists for HF filename
            hf_filename = str(p)
            if p.parts and p.parts[0] == self.local_dir.name:
                hf_filename = str(Path(*p.parts[1:]))

            # Staff Engineer: if it's a collection (no extension), use snapshot_download
            if not p.suffix:
                logger.info("Downloading collection prefix: %s*", hf_filename)
                downloaded_path = snapshot_download(
                    repo_id=self.repo_id,
                    allow_patterns=[f"{hf_filename}*"],
                    local_dir=str(self.local_dir),
                    repo_type="dataset",
                )
            else:
                downloaded_path = hf_hub_download(
                    repo_id=self.repo_id,
                    filename=hf_filename,
                    local_dir=str(self.local_dir),
                    repo_type="dataset",
                )
            res_path = Path(downloaded_path)
            self._cache[asset_path] = res_path
            return res_path
        except Exception as e:
            logger.error("Failed to download asset %s from HF: %s", asset_path, e)
            # Return the local path anyway, it will probably fail later but we tried
            return local_p
