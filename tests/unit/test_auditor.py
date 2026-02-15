"""
Unit tests for the consolidated auditing module.
"""

import polars as pl
import pytest

from render_tag.audit.auditor import (
    AuditDiff,
    AuditReport,
    DatasetAuditor,
    DistributionStats,
    EnvironmentalAudit,
    GeometricAudit,
    IntegrityAudit,
)


@pytest.fixture
def dummy_df():
    data = {
        "lighting_intensity": [10.0, 20.0, 30.0],
        "distance": [1.0, 2.0, 5.0],
        "angle_of_incidence": [10.0, 20.0, 30.0],
        "image_id": ["img1", "img2", "img3"],
    }
    return pl.DataFrame(data)


def test_dataset_auditor_stats(dummy_df, tmp_path):
    """Verify that DatasetAuditor calculates stats correctly via run_audit."""
    # Create dummy dataset structure
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "tags.csv").touch()

    auditor = DatasetAuditor(dataset_dir)
    # Mock load_rich_detections to return our dummy_df
    auditor.reader.load_rich_detections = lambda: dummy_df

    result = auditor.run_audit()
    report = result.report

    assert report.environmental.lighting_intensity.mean == 20.0
    assert report.geometric.distance.max == 5.0
    assert report.geometric.tag_count == 3


def test_audit_diff():
    stats = DistributionStats(min=1, max=10, mean=5, std=2, median=5)
    report_a = AuditReport(
        dataset_name="v1",
        timestamp="t1",
        geometric=GeometricAudit(
            distance=stats, incidence_angle=stats, tag_count=100, image_count=10
        ),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(),
    )
    report_b = AuditReport(
        dataset_name="v2",
        timestamp="t2",
        geometric=GeometricAudit(
            distance=stats, incidence_angle=stats, tag_count=150, image_count=15
        ),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(),
    )

    diff = AuditDiff(report_a, report_b).calculate()
    assert diff["tag_count"] == 50
    assert diff["image_count"] == 5
