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
