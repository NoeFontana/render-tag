import json
from pathlib import Path

import pytest

from render_tag.audit.auditor import DatasetAuditor
from render_tag.core.schema.base import KeypointVisibility


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


def test_dataset_auditor_wrapped_format(tmp_path):
    """Auditor handles the v2 wrapped JSON format (version + evaluation_context + records)."""
    dataset_dir = tmp_path / "wrapped_dataset"
    dataset_dir.mkdir()

    wrapped = {
        "version": "2.0",
        "evaluation_context": {"photometric_margin_px": 0, "truncation_policy": "ternary_visibility"},
        "records": [
            {"image_id": "img1", "tag_id": 0, "distance": 2.5, "angle_of_incidence": 30.0, "lighting_intensity": 100.0},
        ],
    }
    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(wrapped, f)

    auditor = DatasetAuditor(dataset_dir)
    result = auditor.run_audit()

    assert result.report.geometric.tag_count == 1
    assert result.report.geometric.distance.max == 2.5


def test_margin_check_detects_violation(tmp_path):
    """_run_margin_check catches a corner marked VISIBLE inside the eval margin."""
    auditor = DatasetAuditor(tmp_path)

    records = [
        {
            "image_id": "img1",
            "tag_id": 0,
            "record_type": "TAG",
            "resolution": [640, 480],
            "corners": [[5, 240], [320, 10], [635, 240], [320, 470]],
            # corners 0,1,2 are inside the 20px margin but marked VISIBLE — violation
            "corners_visibility": [
                KeypointVisibility.VISIBLE,
                KeypointVisibility.VISIBLE,
                KeypointVisibility.VISIBLE,
                KeypointVisibility.MARGIN_TRUNCATED,
            ],
        }
    ]
    violations = auditor._run_margin_check(records, margin_px=20)
    assert violations == 3


def test_margin_check_no_violations(tmp_path):
    """_run_margin_check passes when visibility flags match the geometry."""
    auditor = DatasetAuditor(tmp_path)

    records = [
        {
            "image_id": "img1",
            "tag_id": 0,
            "record_type": "TAG",
            "resolution": [640, 480],
            "corners": [[5, 240], [320, 50], [620, 240], [320, 430]],
            "corners_visibility": [
                KeypointVisibility.MARGIN_TRUNCATED,  # x=5 < margin=20
                KeypointVisibility.VISIBLE,
                KeypointVisibility.MARGIN_TRUNCATED,  # x=620 >= 640-20=620
                KeypointVisibility.VISIBLE,
            ],
        }
    ]
    violations = auditor._run_margin_check(records, margin_px=20)
    assert violations == 0


def test_margin_check_skipped_when_margin_zero(tmp_path):
    """_run_margin_check is a no-op when margin_px=0 (default config)."""
    auditor = DatasetAuditor(tmp_path)

    # Fabricate a record that would be a violation if margin were active
    records = [
        {
            "image_id": "img1",
            "tag_id": 0,
            "resolution": [640, 480],
            "corners": [[2, 2], [638, 2], [638, 478], [2, 478]],
            "corners_visibility": [2, 2, 2, 2],
        }
    ]
    # margin_px=0 → always 0 violations regardless of geometry
    assert auditor._run_margin_check(records, margin_px=0) == 0


def test_load_raw_records_v1_backward_compat(tmp_path):
    """load_raw_records handles legacy bare-array format, returning empty eval_ctx."""
    dataset_dir = tmp_path / "legacy"
    dataset_dir.mkdir()

    records = [{"image_id": "img1", "tag_id": 0, "corners": [[10, 10], [100, 10], [100, 100], [10, 100]]}]
    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(records, f)

    from render_tag.audit.auditor import DatasetReader
    reader = DatasetReader(dataset_dir)
    raw_records, eval_ctx = reader.load_raw_records()

    assert len(raw_records) == 1
    assert eval_ctx == {}


def test_load_raw_records_v2_format(tmp_path):
    """load_raw_records extracts records and evaluation_context from wrapped format."""
    dataset_dir = tmp_path / "v2"
    dataset_dir.mkdir()

    wrapped = {
        "version": "2.0",
        "evaluation_context": {"photometric_margin_px": 12, "truncation_policy": "ternary_visibility"},
        "records": [{"image_id": "img1", "tag_id": 0}],
    }
    with open(dataset_dir / "rich_truth.json", "w") as f:
        json.dump(wrapped, f)

    from render_tag.audit.auditor import DatasetReader
    reader = DatasetReader(dataset_dir)
    raw_records, eval_ctx = reader.load_raw_records()

    assert len(raw_records) == 1
    assert eval_ctx["photometric_margin_px"] == 12


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
