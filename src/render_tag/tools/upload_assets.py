import argparse
import os
from pathlib import Path

try:
    from huggingface_hub import HfApi
except ImportError:
    HfApi = None


def upload_assets(
    assets_dir: Path,
    repo_id: str,
    token: str | None = None,
    dry_run: bool = False,
) -> None:
    """Upload assets to Hugging Face Hub.

    Args:
        assets_dir: Path to the assets directory
        repo_id: Hugging Face repository ID (e.g. 'username/dataset')
        token: Hugging Face API token (optional, uses env var or local login if None)
        dry_run: If True, only print what would be uploaded
    """
    if not assets_dir.exists():
        print(f"Error: Assets directory not found: {assets_dir}")
        return

    if HfApi is None and not dry_run:
        print("Error: huggingface_hub not installed. Run 'pip install huggingface_hub'.")
        return

    print(f"Preparing to upload assets from {assets_dir} to {repo_id}")

    # Check token
    if not token:
        token = os.environ.get("HF_TOKEN")

    if not token and not dry_run:
        print("Warning: No HF_TOKEN provided and dry_run is False. Assuming local login.")

    if not dry_run:
        api = HfApi(token=token)

    if dry_run:
        print("[DRY RUN] Would upload the following files:")
        for root, _, files in os.walk(assets_dir):
            for file in files:
                local_path = Path(root) / file
                rel_path = local_path.relative_to(assets_dir)
                print(f"  - {rel_path}")
        return

    try:
        print(f"Uploading to {repo_id}...")
        api.upload_folder(
            folder_path=str(assets_dir),
            repo_id=repo_id,
            repo_type="dataset",
            path_in_repo=".",
            commit_message="Update render-tag assets",
        )
        print("Upload complete!")
        print(f"View dataset at: https://huggingface.co/datasets/{repo_id}")

    except Exception as e:
        print(f"Upload failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload assets to Hugging Face Hub")
    parser.add_argument(
        "--assets-dir", type=Path, default="assets", help="Path to assets directory"
    )
    parser.add_argument("--repo-id", required=True, help="Hugging Face repository ID")
    parser.add_argument("--token", help="Hugging Face API token")
    parser.add_argument("--dry-run", action="store_true", help="Preview upload without executing")

    args = parser.parse_args()

    upload_assets(
        assets_dir=args.assets_dir,
        repo_id=args.repo_id,
        token=args.token,
        dry_run=args.dry_run,
    )
