import json

import pytest

from render_tag.data_io.auditor import DatasetAuditor


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
    
    assert parsed["report"]["dataset_name"] == "report_dataset"
    assert "geometric" in parsed["report"]
    assert "environmental" in parsed["report"]
    assert parsed["gate_passed"] is True
