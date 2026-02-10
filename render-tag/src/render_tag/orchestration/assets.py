"""
Asset management and synchronization for render-tag.

Handles bidirectional sync between local file system and Hugging Face Hub.
Enforces strict directory structure for binary assets.
"""

import hashlib
import logging
from pathlib import Path
from typing import ClassVar

try:
    from huggingface_hub import snapshot_download, upload_folder
except ImportError:
    # Allow local development/testing without HF installed
    snapshot_download = None
    upload_folder = None

logger = logging.getLogger(__name__)


class AssetManager:
    """Manages local asset cache and remote synchronization."""

    REQUIRED_SUBDIRS: ClassVar[list[str]] = ["hdri", "textures", "tags", "models"]

    def __init__(self, local_dir: Path, repo_id: str = "NoeFontana/render-tag-assets"):
        self.local_dir = Path(local_dir)
        self.repo_id = repo_id
        self._ensure_structure()

    def _ensure_structure(self):
        """Enforce the directory contract for local assets."""
        self.local_dir.mkdir(parents=True, exist_ok=True)
        for sub in self.REQUIRED_SUBDIRS:
            (self.local_dir / sub).mkdir(exist_ok=True)

    def pull(self, token: str | None = None):
        """Download the latest assets from the remote repository.

        Args:
            token: Hugging Face API token.
        """
        if snapshot_download is None:
            raise ImportError("huggingface_hub not installed. Run 'pip install huggingface_hub'.")

        logger.info(f"Pulling assets from {self.repo_id} to {self.local_dir}")

        snapshot_download(
            repo_id=self.repo_id,
            local_dir=str(self.local_dir),
            token=token,
            repo_type="dataset",
            # We use LFS-aware download by default
        )

    def push(self, token: str, commit_message: str = "Update assets"):
        """Upload local changes to the remote repository.

        Args:
            token: Hugging Face API token (required for write access).
            commit_message: Semantic description of the changes.
        """
        if upload_folder is None:
            raise ImportError("huggingface_hub not installed. Run 'pip install huggingface_hub'.")

        if not token:
            raise ValueError("HF_TOKEN is required for pushing assets.")

        logger.info(f"Pushing assets from {self.local_dir} to {self.repo_id}")

        upload_folder(
            folder_path=str(self.local_dir),
            repo_id=self.repo_id,
            token=token,
            commit_message=commit_message,
            repo_type="dataset",
        )

    def get_assets_hash(self) -> str:
        """
        Calculates a deterministic SHA256 hash of all files in the asset directory.
        Used for the 'Asset Lock' in JobSpec.
        """
        hasher = hashlib.sha256()

        # Walk the directory in a deterministic order
        paths = sorted(
            [p for p in self.local_dir.rglob("*") if p.is_file()],
            key=lambda x: str(x.relative_to(self.local_dir)),
        )

        for path in paths:
            # Hash path (relative) to handle renames/moves
            rel_path = str(path.relative_to(self.local_dir))
            hasher.update(rel_path.encode())

            # Hash content
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)

        return hasher.hexdigest()
