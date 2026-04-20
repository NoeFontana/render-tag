"""``--preset A --preset B`` on the CLI ≡ ``presets: [A, B]`` in YAML."""

from __future__ import annotations

from pathlib import Path

import pytest

from render_tag.core.config_loader import ConfigResolver


@pytest.fixture()
def bare_config(tmp_path: Path) -> Path:
    path = tmp_path / "bare.yaml"
    path.write_text("dataset:\n  num_scenes: 1\n")
    return path


@pytest.fixture()
def yaml_with_presets(tmp_path: Path) -> Path:
    path = tmp_path / "with_presets.yaml"
    path.write_text("dataset:\n  num_scenes: 1\npresets:\n  - lighting.factory\n  - shadow.harsh\n")
    return path


def test_cli_preset_equals_yaml_preset(
    tmp_path: Path, bare_config: Path, yaml_with_presets: Path
) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()

    spec_cli = ConfigResolver(bare_config).resolve(
        output_dir=out_a,
        seed=2026,
        cli_presets=["lighting.factory", "shadow.harsh"],
    )
    spec_yaml = ConfigResolver(yaml_with_presets).resolve(
        output_dir=out_b,
        seed=2026,
    )

    assert spec_cli.applied_presets == ["lighting.factory", "shadow.harsh"]
    assert spec_cli.applied_presets == spec_yaml.applied_presets
    assert spec_cli.scene_config.scene.lighting.model_dump() == (
        spec_yaml.scene_config.scene.lighting.model_dump()
    )


def test_cli_preset_appended_after_yaml_list(tmp_path: Path, yaml_with_presets: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    spec = ConfigResolver(yaml_with_presets).resolve(
        output_dir=out,
        seed=2026,
        cli_presets=["lighting.warehouse"],
    )
    assert spec.applied_presets == [
        "lighting.factory",
        "shadow.harsh",
        "lighting.warehouse",
    ]


def test_applied_presets_affects_job_id(tmp_path: Path, bare_config: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()

    spec_no = ConfigResolver(bare_config).resolve(output_dir=out_a, seed=2026)
    spec_yes = ConfigResolver(bare_config).resolve(
        output_dir=out_b, seed=2026, cli_presets=["lighting.factory"]
    )
    assert spec_no.job_id != spec_yes.job_id
