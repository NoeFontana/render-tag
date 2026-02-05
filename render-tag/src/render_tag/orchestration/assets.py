"""
Asset management and synchronization for render-tag.

Handles bidirectional sync between local file system and Hugging Face Hub.
Enforces strict directory structure for binary assets.
"""

import os
from pathlib import Path
from typing import Optional
import logging

try:
    from huggingface_hub import snapshot_download, upload_folder
except ImportError:
    # Allow local development/testing without HF installed
    snapshot_download = None
    upload_folder = None

logger = logging.getLogger(__name__)

class AssetManager:
    """Manages local asset cache and remote synchronization."""
    
    REQUIRED_SUBDIRS = ["hdri", "textures", "tags", "models"]
    
    def __init__(self, local_dir: Path, repo_id: str = "NoeFontana/render-tag-assets"):
        self.local_dir = Path(local_dir)
        self.repo_id = repo_id
        self._ensure_structure()
        
    def _ensure_structure(self):
        """Enforce the directory contract for local assets."""
        self.local_dir.mkdir(parents=True, exist_ok=True)
        for sub in self.REQUIRED_SUBDIRS:
            (self.local_dir / sub).mkdir(exist_ok=True)
            
    def pull(self, token: Optional[str] = None):
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
            repo_type="dataset"
        )
