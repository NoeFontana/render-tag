"""
Dataset info generation and fingerprinting.
"""

import hashlib
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from render_tag.common.metadata import (
    CameraIntrinsicsMetadata,
    DatasetMetadata,
    ExperimentMetadata,
    ProvenanceMetadata,
    TagSpecificationMetadata,
)
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
    config: Any,
    evaluation_scopes: list[Any] | None = None,
    experiment_info: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    cli_args: list[str] | None = None,
) -> DatasetMetadata:
    """Generate and write manifest.json (formerly dataset_info.json)."""

    env_hash, blenderproc_version = get_env_fingerprint()
    git_info = get_git_info()
    pkg_version = get_package_version()

    # Provenance
    provenance = ProvenanceMetadata(
        git_commit=git_info.get("commit", "unknown"),
        render_tag_version=pkg_version,
        render_tag_env_hash=env_hash,
        blenderproc_version=blenderproc_version,
        command=" ".join(cli_args) if cli_args else "unknown",
    )

    # Intrinsics
    k = config.camera.get_k_matrix()
    intrinsics = CameraIntrinsicsMetadata(
        focal_length_px=[k[0][0], k[1][1]],
        principal_point=[k[0][2], k[1][2]],
        resolution=list(config.camera.resolution),
    )

    # Tag Spec
    tag_spec = TagSpecificationMetadata(
        tag_family=config.tag.family.value,
        tag_size_m=config.tag.size_meters,
    )

    # Experiment
    exp_meta = None
    if experiment_info:
        exp_meta = ExperimentMetadata(
            name=experiment_info.get("name"),
            variant_id=experiment_info.get("variant_id"),
            description=experiment_info.get("description"),
            overrides=experiment_info.get("overrides", {}),
            seed_info={
                "global": config.dataset.seeds.global_seed,
                "layout": config.dataset.seeds.layout_seed,
                "lighting": config.dataset.seeds.lighting_seed,
                "camera": config.dataset.seeds.camera_seed,
                "noise": config.dataset.seeds.noise_seed,
            },
        )

    # Scopes
    scopes = evaluation_scopes or config.dataset.evaluation_scopes

    manifest = DatasetMetadata(
        provenance=provenance,
        camera_intrinsics=intrinsics,
        tag_specification=tag_spec,
        evaluation_scopes=scopes,
        experiment=exp_meta,
        metadata=extra_metadata or {},
    )

    with open(dataset_dir / "manifest.json", "w") as f:
        f.write(manifest.model_dump_json(indent=2))

    return manifest
