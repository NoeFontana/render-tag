
import pytest

from render_tag.data_io.auditor import GateEnforcer
from render_tag.data_io.auditor_schema import (
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
        geometric=GeometricAudit(distance=stats, incidence_angle=stats, tag_count=1000, image_count=100),
        environmental=EnvironmentalAudit(lighting_intensity=stats),
        integrity=IntegrityAudit()
    )

def test_gate_enforcer_passes(sample_report):
    config_data = {
        "rules": [
            {"metric": "tag_count", "min": 500},
            {"metric": "pose_angle_max", "min": 45}
        ]
    }
    enforcer = GateEnforcer(config_data)
    success, failures = enforcer.evaluate(sample_report)
    
    assert success is True
    assert len(failures) == 0

def test_gate_enforcer_fails(sample_report):
    config_data = {
        "rules": [
            {"metric": "tag_count", "min": 2000, "error_msg": "Too few tags!"},
            {"metric": "impossible_poses", "max": 0}
        ]
    }
    enforcer = GateEnforcer(config_data)
    success, failures = enforcer.evaluate(sample_report)
    
    assert success is False
    assert len(failures) == 1
    assert "Too few tags!" in failures[0]
