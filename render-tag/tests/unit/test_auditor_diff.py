import pytest
from render_tag.data_io.auditor import AuditDiff
from render_tag.data_io.auditor_schema import AuditReport, GeometricAudit, EnvironmentalAudit, IntegrityAudit, DistributionStats

@pytest.fixture
def report_v1():
    stats = DistributionStats(min=1, max=10, mean=5, std=2, median=5)
    return AuditReport(
        dataset_name="v1",
        timestamp="t1",
        geometric=GeometricAudit(distance=stats, incidence_angle=stats, tag_count=100, image_count=10),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit()
    )

@pytest.fixture
def report_v2():
    stats = DistributionStats(min=1, max=20, mean=10, std=5, median=10)
    return AuditReport(
        dataset_name="v2",
        timestamp="t2",
        geometric=GeometricAudit(distance=stats, incidence_angle=stats, tag_count=200, image_count=20),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit(impossible_poses=5)
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
