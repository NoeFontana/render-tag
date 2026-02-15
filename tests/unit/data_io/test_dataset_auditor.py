import json
from pathlib import Path

import pytest

from render_tag.audit.auditor import DatasetAuditor


@pytest.fixture
def rich_dataset(tmp_path):
    """Creates a dataset with rich_truth.json."""
    dataset_dir = tmp_path / "rich_dataset"
    dataset_dir.mkdir()

    rich_truth = [
        {
            "image_id": "img1",
            "tag_id": 0,
            "distance": 2.5,
            "angle_of_incidence": 30.0,
            "lighting_intensity": 100.0,
        },
        {
            "image_id": "img2",
            "tag_id": 1,
            "distance": 5.0,
            "angle_of_incidence": 60.0,
            "lighting_intensity": 80.0,
        },
    ]

    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(rich_truth, f)

    return dataset_dir


def test_dataset_auditor_full_run(rich_dataset):
    """Test the full audit orchestration."""
    auditor = DatasetAuditor(rich_dataset)
    result = auditor.run_audit()

    assert result.report.dataset_name == "rich_dataset"
    assert result.report.geometric.tag_count == 2
    assert result.report.geometric.distance.max == 5.0
    assert result.report.environmental.lighting_intensity.mean == 90.0
    assert result.report.score > 0


def test_calculate_score_penalties():
    """Test the heuristic scoring logic."""
    from render_tag.audit.auditor import (
        DatasetAuditor,
        DistributionStats,
        EnvironmentalAudit,
        GeometricAudit,
        IntegrityAudit,
    )

    auditor = DatasetAuditor(Path("."))

    stats = DistributionStats(min=1, max=5, mean=3, std=1, median=3)
    geom = GeometricAudit(distance=stats, incidence_angle=stats, tag_count=10, image_count=5)
    env = EnvironmentalAudit(lighting_intensity=stats)

    # 1. Perfect score (except for variance penalties)
    integrity_clean = IntegrityAudit(impossible_poses=0, orphaned_tags=0, corrupted_frames=0)
    # incidence_angle.max = 5 (< 45), so -20. distance variance is 4 (> 1.0), so no penalty.
    # Score should be 80.
    assert auditor._calculate_score(geom, env, integrity_clean) == 80.0

    # 2. Penalty for impossible poses
    integrity_bad = IntegrityAudit(impossible_poses=2, orphaned_tags=0, corrupted_frames=0)
    # 80 - 2*10 = 60
    assert auditor._calculate_score(geom, env, integrity_bad) == 60.0
