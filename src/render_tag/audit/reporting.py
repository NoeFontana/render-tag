"""
Unified reporting and dataset inspection for render-tag.

Provides manifest generation, directory hashing, and interactive HTML dashboards.
"""

import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    go = None
    make_subplots = None

from render_tag.core.metadata import (
    CameraIntrinsicsMetadata,
    DatasetManifest,
    ExperimentMetadata,
    ProvenanceMetadata,
    TagSpecificationMetadata,
)
from render_tag.core.schema.job import get_env_fingerprint

from .auditor import AuditResult, DatasetReader


def get_package_version() -> str:
    try:
        return version("render-tag")
    except PackageNotFoundError:
        return "unknown"


def get_git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def generate_dataset_info(
    dataset_dir: Path,
    config: Any,
    evaluation_scopes: list[Any] | None = None,
    experiment_info: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    cli_args: list[str] | None = None,
) -> DatasetManifest:
    """Generate and write manifest.json."""
    env_hash, blenderproc_version = get_env_fingerprint()
    pkg_version = get_package_version()

    provenance = ProvenanceMetadata(
        git_commit=get_git_commit(),
        render_tag_version=pkg_version,
        render_tag_env_hash=env_hash,
        blenderproc_version=blenderproc_version,
        command=" ".join(cli_args) if cli_args else "unknown",
    )

    k = config.camera.get_k_matrix()
    width, height = config.camera.resolution
    intrinsics = CameraIntrinsicsMetadata(
        fx=k[0][0], fy=k[1][1], cx=k[0][2], cy=k[1][2], width=width, height=height
    )

    from render_tag.core.schema.subject import BoardSubjectConfig, TagSubjectConfig

    subject = config.scenario.subject.root if config.scenario.subject else None
    if isinstance(subject, TagSubjectConfig):
        tag_family = subject.tag_families[0] if subject.tag_families else "tag36h11"
        tag_size_m = subject.size_mm / 1000.0
    elif isinstance(subject, BoardSubjectConfig):
        tag_family = subject.dictionary
        tag_size_m = subject.marker_size_mm / 1000.0
    else:
        tag_family = "tag36h11"
        tag_size_m = 0.1
    tag_spec = TagSpecificationMetadata(tag_family=tag_family, tag_size_m=tag_size_m)

    exp_meta = None
    if experiment_info:
        exp_meta = ExperimentMetadata(
            name=experiment_info.get("name"),
            variant_id=experiment_info.get("variant_id"),
            description=experiment_info.get("description"),
            overrides=experiment_info.get("overrides", {}),
        )

    manifest = DatasetManifest(
        provenance=provenance,
        camera_intrinsics=intrinsics,
        tag_specification=tag_spec,
        evaluation_scopes=evaluation_scopes or config.dataset.evaluation_scopes,
        experiment=exp_meta,
        metadata=extra_metadata or {},
    )

    dataset_dir.mkdir(parents=True, exist_ok=True)
    with open(dataset_dir / "manifest.json", "w") as f:
        f.write(manifest.model_dump_json(indent=2))
    return manifest


class DashboardGenerator:
    """Generates a standalone HTML dashboard from an AuditResult."""

    def __init__(self, dataset_path: Path, result: AuditResult) -> None:
        self.dataset_path = dataset_path
        self.result = result
        self.reader = DatasetReader(dataset_path)

    def generate(self, filename: str = "audit_dashboard.html") -> Path:
        if go is None:
            raise ImportError("plotly required")

        df = self.reader.load_rich_detections()
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=("Distance", "Angle", "Lighting", "Summary"),
            specs=[
                [{"type": "histogram"}, {"type": "histogram"}],
                [{"type": "histogram"}, {"type": "table"}],
            ],
        )

        if "distance" in df.columns:
            fig.add_trace(go.Histogram(x=df["distance"], name="Dist"), row=1, col=1)
        if "angle_of_incidence" in df.columns:
            fig.add_trace(go.Histogram(x=df["angle_of_incidence"], name="Angle"), row=1, col=2)
        if "ppm" in df.columns:
            fig.add_trace(go.Histogram(x=df["ppm"], name="PPM"), row=2, col=1)

        report = self.result.report
        fig.add_trace(
            go.Table(
                header={"values": ["Metric", "Value"]},
                cells={
                    "values": [
                        ["Score", "Tags", "Images"],
                        [
                            f"{report.score:.1f}",
                            report.geometric.tag_count,
                            report.geometric.image_count,
                        ],
                    ]
                },
            ),
            row=2,
            col=2,
        )

        output_path = self.dataset_path / filename
        fig.write_html(str(output_path))
        return output_path
