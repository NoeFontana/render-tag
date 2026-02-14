import polars as pl

from render_tag.audit.auditor import EnvironmentalAuditor, IntegrityAuditor


def test_environmental_auditor_stats():
    """Verify that EnvironmentalAuditor calculates lighting stats."""
    data = {"lighting_intensity": [10.0, 20.0, 30.0], "image_id": ["img1", "img2", "img3"]}
    df = pl.DataFrame(data)

    auditor = EnvironmentalAuditor(df)
    results = auditor.audit()

    assert results.lighting_intensity.min == 10.0
    assert results.lighting_intensity.max == 30.0
    assert results.lighting_intensity.mean == 20.0


def test_integrity_auditor_impossible_poses():
    """Verify that IntegrityAuditor detects tags behind camera (z < 0)."""
    # In our rich metadata, distance is usually positive.
    # Let's assume we add a 'z_depth' or similar if we want to catch bugs.
    # For now, we can use distance < 0 as a sanity check if it ever happens.
    data = {"distance": [-1.0, 2.0, 5.0], "image_id": ["img1", "img2", "img3"]}
    df = pl.DataFrame(data)

    auditor = IntegrityAuditor(df)
    results = auditor.audit()

    assert results.impossible_poses == 1
import pytest

from render_tag.audit.auditor import AuditDiff
from render_tag.audit.auditor_schema import (
    AuditReport,
    DistributionStats,
    EnvironmentalAudit,
    GeometricAudit,
    IntegrityAudit,
)


@pytest.fixture
def report_v1():
    stats = DistributionStats(min=1, max=10, mean=5, std=2, median=5)
    return AuditReport(
        dataset_name="v1",
        timestamp="t1",
        geometric=GeometricAudit(
            distance=stats, incidence_angle=stats, tag_count=100, image_count=10
        ),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(),
    )


@pytest.fixture
def report_v2():
    stats = DistributionStats(min=1, max=20, mean=10, std=5, median=10)
    return AuditReport(
        dataset_name="v2",
        timestamp="t2",
        geometric=GeometricAudit(
            distance=stats, incidence_angle=stats, tag_count=200, image_count=20
        ),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(impossible_poses=5),
    )


def test_audit_diff_calculates_deltas(report_v1, report_v2):
    """Verify that AuditDiff calculates correct deltas between two reports."""
    diff = AuditDiff(report_v1, report_v2)
    delta = diff.calculate()

    assert delta["tag_count"] == 100
    assert delta["image_count"] == 10
    assert delta["distance_mean_diff"] == 5.0
    assert delta["incidence_angle_max_diff"] == 10.0
    assert delta["impossible_poses_diff"] == 5
import pytest

from render_tag.audit.auditor import GateEnforcer
from render_tag.audit.auditor_schema import (
    AuditReport,
    DistributionStats,
    EnvironmentalAudit,
    GeometricAudit,
    IntegrityAudit,
)


@pytest.fixture
def sample_report():
    stats = DistributionStats(min=1, max=50, mean=25, std=10, median=25)
    return AuditReport(
        dataset_name="test",
        timestamp="now",
        geometric=GeometricAudit(
            distance=stats, incidence_angle=stats, tag_count=1000, image_count=100
        ),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(),
    )


def test_gate_enforcer_passes(sample_report):
    config_data = {
        "rules": [{"metric": "tag_count", "min": 500}, {"metric": "pose_angle_max", "min": 45}]
    }
    enforcer = GateEnforcer(config_data)
    success, failures = enforcer.evaluate(sample_report)

    assert success is True
    assert len(failures) == 0


def test_gate_enforcer_fails(sample_report):
    config_data = {
        "rules": [
            {"metric": "tag_count", "min": 2000, "error_msg": "Too few tags!"},
            {"metric": "impossible_poses", "max": 0},
        ]
    }
    enforcer = GateEnforcer(config_data)
    success, failures = enforcer.evaluate(sample_report)

    assert success is False
    assert len(failures) == 1
    assert "Too few tags!" in failures[0]
import polars as pl

from render_tag.audit.auditor import GeometryAuditor


def test_geometry_auditor_calculates_stats():
    """Verify that GeometryAuditor calculates basic stats for distance and angle."""
    data = {
        "distance": [1.0, 2.0, 3.0, 4.0, 5.0],
        "angle_of_incidence": [10.0, 20.0, 30.0, 40.0, 50.0],
        "image_id": ["img1", "img1", "img2", "img2", "img3"],
    }
    df = pl.DataFrame(data)

    auditor = GeometryAuditor(df)
    results = auditor.audit()

    assert results.tag_count == 5
    assert results.image_count == 3

    assert results.distance.min == 1.0
    assert results.distance.max == 5.0
    assert results.distance.mean == 3.0

    assert results.incidence_angle.min == 10.0
    assert results.incidence_angle.max == 50.0
    assert results.incidence_angle.mean == 30.0
import json

import polars as pl
import pytest

from render_tag.audit.auditor import DatasetReader


@pytest.fixture
def dummy_dataset(tmp_path):
    """Creates a dummy dataset for testing ingestion."""
    dataset_dir = tmp_path / "dataset_v1"
    dataset_dir.mkdir()

    # Create tags.csv
    tags_path = dataset_dir / "tags.csv"
    tags_content = [
        ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"],
        [
            "scene_0000_cam_0000",
            "0",
            "apriltag_36h11",
            "100",
            "100",
            "200",
            "100",
            "200",
            "200",
            "100",
            "200",
        ],
        [
            "scene_0000_cam_0000",
            "1",
            "apriltag_36h11",
            "300",
            "300",
            "400",
            "300",
            "400",
            "400",
            "300",
            "400",
        ],
        [
            "scene_0001_cam_0000",
            "0",
            "apriltag_36h11",
            "150",
            "150",
            "250",
            "150",
            "250",
            "250",
            "150",
            "250",
        ],
    ]
    import csv

    with open(tags_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(tags_content)

    # Create manifest.json
    manifest_path = dataset_dir / "manifest.json"
    manifest_data = {
        "experiment_name": "test_exp",
        "variant_id": "v000",
        "config": {"dataset": {"name": "test"}},
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)

    # Create sidecar metadata
    images_dir = dataset_dir / "images"
    images_dir.mkdir()

    meta_0 = images_dir / "scene_0000_cam_0000_meta.json"
    with open(meta_0, "w") as f:
        json.dump({"recipe_snapshot": {"world": {"lighting": {"intensity": 100.0}}}}, f)

    meta_1 = images_dir / "scene_0001_cam_0000_meta.json"
    with open(meta_1, "w") as f:
        json.dump({"recipe_snapshot": {"world": {"lighting": {"intensity": 50.0}}}}, f)

    return dataset_dir


def test_dataset_reader_loads_csv(dummy_dataset):
    """Verify that DatasetReader can load tags.csv into a Polars DataFrame."""
    reader = DatasetReader(dummy_dataset)
    df = reader.load_detections()

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 3
    assert "image_id" in df.columns
    assert "tag_id" in df.columns


def test_dataset_reader_joins_metadata(dummy_dataset):
    """Verify that DatasetReader can join sidecar metadata."""
    reader = DatasetReader(dummy_dataset)
    df = reader.load_full_dataset()

    assert "lighting_intensity" in df.columns
    # Check that lighting intensity matches for each row
    scene_0 = df.filter(pl.col("image_id") == "scene_0000_cam_0000")
    assert scene_0["lighting_intensity"][0] == 100.0

    scene_1 = df.filter(pl.col("image_id") == "scene_0001_cam_0000")
    assert scene_1["lighting_intensity"][0] == 50.0
import polars as pl

from render_tag.audit.auditor import OutlierExporter


def test_outlier_exporter_identifies_and_links(tmp_path):
    """Verify that OutlierExporter identifies outliers and creates symlinks."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    images_dir = dataset_dir / "images"
    images_dir.mkdir()

    # Create dummy images
    (images_dir / "img1.png").touch()
    (images_dir / "img2.png").touch()

    data = {
        "image_id": ["img1", "img2"],
        "distance": [-1.0, 5.0],  # img1 is an outlier
    }
    df = pl.DataFrame(data)

    exporter = OutlierExporter(dataset_dir, df)
    outlier_dir = exporter.export()

    assert outlier_dir.exists()
    assert (outlier_dir / "img1.png").exists()
    assert not (outlier_dir / "img2.png").exists()
    # Check if it is a symlink
    assert (outlier_dir / "img1.png").is_symlink()
import json

import pytest

from render_tag.audit.auditor import DatasetAuditor


@pytest.fixture
def rich_dataset(tmp_path):
    dataset_dir = tmp_path / "report_dataset"
    dataset_dir.mkdir()
    rich_truth = [{"image_id": "img1", "tag_id": 0, "distance": 2.5, "angle_of_incidence": 30.0}]
    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(rich_truth, f)
    return dataset_dir


def test_audit_report_json_serialization(rich_dataset):
    """Verify that AuditResult can be serialized to JSON."""
    auditor = DatasetAuditor(rich_dataset)
    result = auditor.run_audit()

    # Check serialization
    json_data = result.model_dump_json()
    parsed = json.loads(json_data)

    assert parsed["report"]["dataset_name"] == "viz_dataset"
    assert "geometric" in parsed["report"]
    assert "environmental" in parsed["report"]
    assert parsed["gate_passed"] is True
import json

import pytest

from render_tag.audit.auditor import DatasetAuditor
from render_tag.audit.auditor_viz import DashboardGenerator


@pytest.fixture
def rich_dataset(tmp_path):
    dataset_dir = tmp_path / "viz_dataset"
    dataset_dir.mkdir()
    rich_truth = [
        {
            "image_id": "img1",
            "tag_id": 0,
            "distance": 2.5,
            "angle_of_incidence": 30.0,
            "lighting_intensity": 100,
        },
        {
            "image_id": "img2",
            "tag_id": 1,
            "distance": 5.0,
            "angle_of_incidence": 60.0,
            "lighting_intensity": 80,
        },
    ]
    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(rich_truth, f)
    return dataset_dir


def test_dashboard_generator_creates_file(rich_dataset):
    """Verify that DashboardGenerator creates an HTML file."""
    auditor = DatasetAuditor(rich_dataset)
    result = auditor.run_audit()

    generator = DashboardGenerator(rich_dataset, result)
    html_path = generator.generate()

    assert html_path.exists()
    assert html_path.suffix == ".html"
    assert html_path.stat().st_size > 0
    with open(html_path) as f:
        content = f.read()
        assert "Plotly" in content
        assert "AUDIT REPORT" in content
