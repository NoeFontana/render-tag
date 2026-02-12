"""
Dataset info generation and fingerprinting.
"""

import hashlib
import json
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from render_tag.schema.job import get_env_fingerprint


def get_package_version() -> str:
    try:
        return version("render-tag")
    except PackageNotFoundError:
        return "unknown"


def calculate_directory_hash(directory: Path) -> str:
    """Calculate SHA256 hash of all files in a directory (recursively)."""
    hasher = hashlib.sha256()

    # Sort paths for determinism
    files = sorted(
        [p for p in directory.rglob("*") if p.is_file() and p.name != "dataset_info.json"]
    )

    for p in files:
        # Update with filename (relative)
        rel_path = p.relative_to(directory).as_posix()
        hasher.update(rel_path.encode("utf-8"))

        # Update with content
        with open(p, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

    return hasher.hexdigest()


def get_git_info() -> dict[str, str]:
    try:
        sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
        return {"commit": sha}
    except Exception:
        return {"commit": "unknown"}


def generate_dataset_info(
    dataset_dir: Path,
    evaluation_scopes: list[str] | None = None,
    intent: str | None = None,
    geometry: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate and write dataset_info.json."""

    env_hash, blenderproc_version = get_env_fingerprint()
    git_info = get_git_info()
    pkg_version = get_package_version()

    integrity_hash = calculate_directory_hash(dataset_dir)

    # Hybrid logic: prefer evaluation_scopes, fallback to mapping intent if available
    scopes = evaluation_scopes or []
    if not scopes and intent:
        # Simple heuristic mapping for ad-hoc generation if scopes not provided
        if intent == "calibration":
            scopes = ["calibration"]
        elif "pose" in intent:
            scopes = ["detection", "pose_estimation", "corner_accuracy"]
        else:
            scopes = ["detection"]

    info = {
        "evaluation_scopes": scopes,
        "intent": intent or (scopes[0] if scopes else "unknown"),
        "geometry": geometry or {},
        "provenance": {
            "git": git_info,
            "render_tag_version": pkg_version,
            "render_tag_env_hash": env_hash,
            "blenderproc_version": blenderproc_version,
            "pose_convention": "xyzw",
        },
        "integrity": {
            "sha256": integrity_hash,
        },
        "metadata": extra_metadata or {},
    }

    with open(dataset_dir / "dataset_info.json", "w") as f:
        json.dump(info, f, indent=2)

    return info
