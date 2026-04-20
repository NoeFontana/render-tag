"""Unit tests for `CampaignMatrix` Cartesian expansion.

The matrix path in `expand_campaign` does not hit Pydantic-level
`GenConfig.model_validate` for pure expansion (only when the variant is
materialized against a real config). These tests isolate the expansion
helper so axis-naming and override-merging can be asserted without
loading any YAML from disk.
"""

from __future__ import annotations

from render_tag.orchestration.experiment import _expand_matrix
from render_tag.orchestration.experiment_schema import (
    CampaignAxis,
    CampaignMatrix,
    SubExperiment,
)


def _make_matrix(
    axes: list[CampaignAxis],
    *,
    base_overrides: dict | None = None,
    name: str = "bench",
    config: str = "configs/benchmarks/dummy.yaml",
) -> CampaignMatrix:
    return CampaignMatrix(
        base=SubExperiment.model_validate(
            {"name": name, "config": config, "overrides": base_overrides or {}}
        ),
        axes=axes,
    )


def test_single_axis_expansion_count_and_override():
    matrix = _make_matrix(
        [CampaignAxis(parameter="camera.resolution", values=[[640, 480], [1920, 1080]])]
    )

    variants = _expand_matrix(matrix)

    assert len(variants) == 2
    assert variants[0].overrides == {"camera": {"resolution": [640, 480]}}
    assert variants[1].overrides == {"camera": {"resolution": [1920, 1080]}}


def test_two_axis_cartesian_product():
    matrix = _make_matrix(
        [
            CampaignAxis(parameter="camera.iso", values=[100, 800, 3200]),
            CampaignAxis(parameter="camera.fov", values=[60.0, 90.0]),
        ]
    )

    variants = _expand_matrix(matrix)

    assert len(variants) == 6
    combos = {(v.overrides["camera"]["iso"], v.overrides["camera"]["fov"]) for v in variants}
    assert combos == {
        (100, 60.0),
        (100, 90.0),
        (800, 60.0),
        (800, 90.0),
        (3200, 60.0),
        (3200, 90.0),
    }


def test_base_overrides_merge_with_axis_overrides():
    matrix = _make_matrix(
        [CampaignAxis(parameter="camera.iso", values=[800])],
        base_overrides={"dataset": {"num_scenes": 5}, "camera": {"fov": 85.0}},
    )

    [variant] = _expand_matrix(matrix)

    assert variant.overrides == {
        "dataset": {"num_scenes": 5},
        "camera": {"fov": 85.0, "iso": 800},
    }


def test_variant_names_are_deterministic_and_distinct():
    matrix = _make_matrix(
        [CampaignAxis(parameter="camera.resolution", values=[[640, 480], [1920, 1080]])],
        name="locus_v1_tag36h11",
    )

    variants = _expand_matrix(matrix)

    names = [v.name for v in variants]
    assert names == [
        "locus_v1_tag36h11__camera_resolution-640x480",
        "locus_v1_tag36h11__camera_resolution-1920x1080",
    ]


def test_variants_do_not_share_override_state():
    """Regression: each variant's overrides must be a fresh tree.

    Axis writes on variant N must not leak into variant N+1. A shared dict
    would silently accumulate the last axis value across the Cartesian
    expansion.
    """
    matrix = _make_matrix(
        [CampaignAxis(parameter="camera.iso", values=[100, 3200])],
        base_overrides={"camera": {"fov": 70.0}},
    )

    variants = _expand_matrix(matrix)

    assert variants[0].overrides["camera"]["iso"] == 100
    assert variants[1].overrides["camera"]["iso"] == 3200
    variants[0].overrides["camera"]["iso"] = 999
    assert variants[1].overrides["camera"]["iso"] == 3200
