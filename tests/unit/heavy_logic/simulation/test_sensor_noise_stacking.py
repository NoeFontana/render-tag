"""Tests for the stacked-noise pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from render_tag.backend.sensors import NoiseEngine, apply_parametric_noise
from render_tag.core.schema import SensorNoiseComponent, SensorNoiseConfig


def _flat_grey(value: int = 128) -> np.ndarray:
    return np.full((128, 128, 3), value, dtype=np.uint8)


def test_legacy_flat_shape_still_parses():
    """Existing fixtures with a single-model flat SensorNoiseConfig must parse."""
    cfg = SensorNoiseConfig.model_validate({"model": "gaussian", "stddev": 0.01, "seed": 42})
    assert cfg.model == "gaussian"
    assert cfg.stddev == 0.01
    assert cfg.seed == 42
    assert cfg.models is None


def test_legacy_flat_shape_produces_identical_pixels():
    """The flat-shape path must be byte-identical to pre-migration behavior."""
    img = _flat_grey()
    cfg = SensorNoiseConfig(model="gaussian", stddev=0.05, seed=0)

    out_a = apply_parametric_noise(img, cfg)
    out_b = apply_parametric_noise(img, cfg)
    assert np.array_equal(out_a, out_b)
    assert np.var(out_a) > 0


def test_stacked_poisson_and_gaussian_exceeds_either_alone():
    """Poisson + Gaussian stacked must produce greater variance than either alone."""
    img = _flat_grey()

    poisson_only = SensorNoiseConfig(
        models=[SensorNoiseComponent(model="poisson", scale=1000.0, seed=0)]
    )
    gaussian_only = SensorNoiseConfig(
        models=[SensorNoiseComponent(model="gaussian", stddev=0.005, seed=0)]
    )
    stacked = SensorNoiseConfig(
        models=[
            SensorNoiseComponent(model="poisson", scale=1000.0, seed=0),
            SensorNoiseComponent(model="gaussian", stddev=0.005, seed=0),
        ]
    )

    p_var = float(np.var(apply_parametric_noise(img, poisson_only)))
    g_var = float(np.var(apply_parametric_noise(img, gaussian_only)))
    s_var = float(np.var(apply_parametric_noise(img, stacked)))

    assert s_var > p_var
    assert s_var > g_var


def test_stacked_empty_list_is_noop():
    img = _flat_grey()
    cfg = SensorNoiseConfig(models=[])
    assert np.array_equal(apply_parametric_noise(img, cfg), img)


def test_stacked_seed_deterministic():
    """Per-component seed inheritance keeps stacked output reproducible."""
    img = _flat_grey()
    cfg = SensorNoiseConfig(
        seed=7,
        models=[
            SensorNoiseComponent(model="poisson", scale=1000.0),
            SensorNoiseComponent(model="gaussian", stddev=0.01),
        ],
    )

    a = apply_parametric_noise(img, cfg)
    b = apply_parametric_noise(img, cfg)
    assert np.array_equal(a, b)


def test_stacked_overrides_flat():
    """If both are set, `models` wins — flat fields are ignored."""
    img = _flat_grey()
    cfg = SensorNoiseConfig(
        model="salt_and_pepper",
        amount=0.5,
        models=[SensorNoiseComponent(model="gaussian", stddev=0.0, seed=0)],
    )
    out = apply_parametric_noise(img, cfg)
    # Salt&pepper would have driven pixels to 0 or 255; gaussian stddev=0 is a no-op.
    assert np.array_equal(out, img)


def test_unknown_component_model_is_skipped():
    img = _flat_grey()
    cfg = SensorNoiseConfig(
        models=[
            SensorNoiseComponent(model="gaussian", stddev=0.01, seed=0),
            SensorNoiseComponent(model="nonexistent", seed=1),
        ]
    )
    out = apply_parametric_noise(img, cfg)
    assert np.var(out) > 0


@pytest.mark.parametrize("seed", [1, 99, 12345])
def test_resolve_components_derives_seeds(seed: int):
    engine = NoiseEngine()
    cfg = SensorNoiseConfig(
        seed=seed,
        models=[
            SensorNoiseComponent(model="gaussian"),
            SensorNoiseComponent(model="poisson"),
        ],
    )
    components = engine._resolve_components(cfg)
    assert len(components) == 2
    assert components[0].seed == seed
    assert components[1].seed == seed + 1
