from pathlib import Path

from render_tag.core.config_loader import ConfigResolver


def test_resolve_absolute_paths(tmp_path):
    # Create a dummy config
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        f.write("dataset:\n  output_dir: ./relative_out\n")

    resolver = ConfigResolver(config_path)
    spec = resolver.resolve(output_dir=tmp_path / "output")

    # Check if output_dir in paths is absolute (it is enforced by resolve arg)
    assert spec.paths.output_dir.is_absolute()
    assert spec.paths.output_dir == (tmp_path / "output").resolve()

    # Check if paths inside scene_config are resolved
    # We wrote ./relative_out to dataset.output_dir
    # The resolver should have made it absolute relative to CWD (or we can assert it is absolute)
    assert spec.scene_config.dataset.output_dir.is_absolute()


def test_overrides():
    resolver = ConfigResolver()  # No config path, uses default
    spec = resolver.resolve(
        output_dir=Path("/tmp/out"),
        scene_limit=5,
        seed=123,
    )

    assert spec.scene_config.dataset.num_scenes == 5
    assert spec.scene_config.dataset.seeds.global_seed == 123
    assert spec.global_seed == 123


def test_auto_seed():
    resolver = ConfigResolver()
    spec1 = resolver.resolve(output_dir=Path("/tmp/out"), seed="auto")
    spec2 = resolver.resolve(output_dir=Path("/tmp/out"), seed="auto")

    # Seeds should likley be different (unless we were extremely unlucky)
    assert spec1.global_seed != spec2.global_seed
