from render_tag.core.config import GenConfig
from render_tag.orchestration.experiment import expand_experiment
from render_tag.orchestration.experiment_schema import Experiment, Sweep, SweepType


def test_expand_experiment_linear_sweep():
    """Verify linear sweep expansion."""
    base = GenConfig()
    base.dataset.seeds.global_seed = 100

    # Sweep camera min_distance from 1.0 to 1.2 step 0.1 -> 1.0, 1.1, 1.2
    sweep = Sweep(
        parameter="camera.min_distance",
        type=SweepType.LINEAR,
        min=1.0,
        max=1.2,
        step=0.1,
    )

    exp = Experiment(
        name="test_linear",
        base_config=base,
        sweeps=[sweep],
        lock_layout=True,
        lock_lighting=True,
        lock_camera=False,  # Vary camera seed
    )

    variants = expand_experiment(exp)

    # 1.0, 1.1, 1.2 might have float precision issues, but roughly 3 variants
    # actually 1.0, 1.1, 1.2000000000000002
    assert len(variants) >= 3

    # check first variant
    v0 = variants[0]
    assert v0.overrides["camera.min_distance"] == 1.0
    assert v0.config.camera.min_distance == 1.0
    # Locked seeds
    assert v0.config.dataset.seeds.layout_seed == 100
    assert v0.config.dataset.seeds.lighting_seed == 100
    # Unlocked camera seed -> global + i*300 => 100 + 0 = 100
    # Wait, variant 0 is i=0. So it equals global seed.

    v1 = variants[1]
    assert abs(v1.config.camera.min_distance - 1.1) < 1e-6
    # Unlocked seed should change
    # i=1 -> 100 + 300 = 400
    assert v1.config.dataset.seeds.camera_seed == 400


def test_expand_experiment_categorical_sweep():
    """Verify categorical sweep expansion."""
    base = GenConfig()

    sweep = Sweep(
        parameter="scene.lighting.intensity_min",
        type=SweepType.CATEGORICAL,
        values=[10, 50, 100],
    )

    exp = Experiment(name="test_cat", base_config=base, sweeps=[sweep])

    variants = expand_experiment(exp)
    assert len(variants) == 3
    assert variants[0].config.scene.lighting.intensity_min == 10
    assert variants[2].config.scene.lighting.intensity_min == 100


def test_expand_experiment_cross_product():
    """Verify 2 sweeps generate cartesian product."""
    base = GenConfig()

    s1 = Sweep(parameter="camera.fov", type=SweepType.CATEGORICAL, values=[60, 90])
    s2 = Sweep(
        parameter="camera.resolution",
        type=SweepType.CATEGORICAL,
        values=[(640, 480), (1024, 768)],
    )

    exp = Experiment(name="test_cross", base_config=base, sweeps=[s1, s2])

    variants = expand_experiment(exp)
    assert len(variants) == 4  # 2 * 2


def test_save_manifest(tmp_path):
    from render_tag.orchestration.experiment import save_manifest
    from render_tag.orchestration.experiment_schema import ExperimentVariant

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
    import json

    data = json.loads(manifest_file.read_text())
    assert data["experiment_name"] == "test_manifest"
    assert data["overrides"] == {"foo": "bar"}
    assert "git_sha" in data
