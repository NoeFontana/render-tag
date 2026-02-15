"""
Unit tests for the experiment module.
"""


import json

from render_tag.core.config import GenConfig
from render_tag.orchestration.experiment import expand_experiment, save_manifest
from render_tag.orchestration.experiment_schema import (
    Experiment,
    ExperimentVariant,
    Sweep,
    SweepType,
)


def test_expand_experiment_no_sweeps():
    base = GenConfig()
    exp = Experiment(name="test_exp", base_config=base, sweeps=[])

    variants = expand_experiment(exp)
    assert len(variants) == 1
    assert variants[0].variant_id == "base"
    assert variants[0].experiment_name == "test_exp"


def test_expand_experiment_with_sweeps():
    base = GenConfig()
    s1 = Sweep(parameter="camera.fov", type=SweepType.CATEGORICAL, values=[40, 50])
    s2 = Sweep(parameter="tag.size_meters", type=SweepType.CATEGORICAL, values=[0.1, 0.2])
    exp = Experiment(name="test_cross", base_config=base, sweeps=[s1, s2])

    variants = expand_experiment(exp)
    assert len(variants) == 4  # 2 * 2


def test_save_manifest(tmp_path):
    base = GenConfig()
    variant = ExperimentVariant(
        experiment_name="test_manifest",
        variant_id="v001",
        description="Test desc",
        config=base,
        overrides={"foo": "bar"},
    )

    save_manifest(tmp_path, variant, cli_args=["render-tag", "experiment"])

    manifest_file = tmp_path / "manifest.json"
    assert manifest_file.exists()

    data = json.loads(manifest_file.read_text())
    
    assert data["experiment"]["name"] == "test_manifest"
    assert data["experiment"]["overrides"] == {"foo": "bar"}
    assert "git_commit" in data["provenance"]
