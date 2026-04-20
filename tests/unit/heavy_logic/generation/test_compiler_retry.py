"""Tests for SceneCompiler.compile_scene(validate=...) retry semantics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from render_tag.core.config import GenConfig
from render_tag.core.seeding import derive_seed
from render_tag.generation.compiler import MAX_VALIDATION_RETRIES, SceneCompiler


def _make_config() -> GenConfig:
    cfg = GenConfig()
    cfg.dataset.num_scenes = 10
    cfg.scene.texture_dir = None
    cfg.scene.background_hdri = None
    return cfg


def test_validate_false_skips_validation_and_returns_first_build(tmp_path: Path) -> None:
    """validate=False must not call RecipeValidator and must use the bare scene seed."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    with patch("render_tag.core.validator.RecipeValidator") as mock_validator:
        recipe = compiler.compile_scene(3, validate=False)

    assert mock_validator.call_count == 0
    assert recipe.scene_id == 3
    # validate=False uses scene_seed directly, not derive_seed(scene_seed, "attempt", 0).
    assert recipe.random_seed == derive_seed(42, "scene", 3)


def test_validate_true_uses_attempt_seed_even_on_first_success(tmp_path: Path) -> None:
    """validate=True always routes through derive_seed(scene_seed, "attempt", n)."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)
    recipe = compiler.compile_scene(0, validate=True)

    scene_seed = derive_seed(42, "scene", 0)
    expected_attempt0 = derive_seed(scene_seed, "attempt", 0)
    assert recipe.random_seed == expected_attempt0


def test_validate_true_retries_then_succeeds(tmp_path: Path) -> None:
    """Simulated errors on the first two attempts must trigger re-sampling with new
    attempt seeds; the successful third attempt returns its recipe."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    class FakeValidator:
        calls = 0

        def __init__(self, recipe):
            self.recipe = recipe
            self.errors: list[str] = []
            self.warnings: list[str] = []

        def validate(self) -> bool:
            FakeValidator.calls += 1
            if FakeValidator.calls < 3:
                self.errors = ["simulated failure"]
                return False
            return True

    with patch("render_tag.core.validator.RecipeValidator", FakeValidator):
        recipe = compiler.compile_scene(0, validate=True)

    assert FakeValidator.calls == 3
    scene_seed = derive_seed(42, "scene", 0)
    assert recipe.random_seed == derive_seed(scene_seed, "attempt", 2)


def test_validate_true_cache_warning_is_not_a_retry_trigger(tmp_path: Path) -> None:
    """Warnings containing 'Cache asset not yet present' must be ignored."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    class FakeValidator:
        calls = 0

        def __init__(self, recipe):
            self.recipe = recipe
            self.errors: list[str] = []
            self.warnings: list[str] = ["Cache asset not yet present: /tmp/foo.png"]

        def validate(self) -> bool:
            FakeValidator.calls += 1
            return True

    with patch("render_tag.core.validator.RecipeValidator", FakeValidator):
        recipe = compiler.compile_scene(0, validate=True)

    assert FakeValidator.calls == 1
    scene_seed = derive_seed(42, "scene", 0)
    assert recipe.random_seed == derive_seed(scene_seed, "attempt", 0)


def test_validate_true_raises_after_exhausting_retries(tmp_path: Path) -> None:
    """Exhausting MAX_VALIDATION_RETRIES must raise RuntimeError (breaking change
    from Generator, which silently returned the last failed recipe)."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    class AlwaysFails:
        def __init__(self, recipe):
            self.recipe = recipe
            self.errors: list[str] = ["always broken"]
            self.warnings: list[str] = []

        def validate(self) -> bool:
            return False

    with (
        patch("render_tag.core.validator.RecipeValidator", AlwaysFails),
        pytest.raises(RuntimeError, match=f"after {MAX_VALIDATION_RETRIES} attempts"),
    ):
        compiler.compile_scene(0, validate=True)


def test_validate_true_retries_on_non_cache_warning(tmp_path: Path) -> None:
    """Any warning other than the cache-pending one must trigger a retry."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    class WarnOnce:
        calls = 0

        def __init__(self, recipe):
            self.recipe = recipe
            self.errors: list[str] = []
            WarnOnce.calls += 1
            self.warnings: list[str] = ["Tag partially occluded"] if WarnOnce.calls == 1 else []

        def validate(self) -> bool:
            return True

    with patch("render_tag.core.validator.RecipeValidator", WarnOnce):
        recipe = compiler.compile_scene(0, validate=True)

    assert WarnOnce.calls == 2
    scene_seed = derive_seed(42, "scene", 0)
    assert recipe.random_seed == derive_seed(scene_seed, "attempt", 1)


def test_compile_shards_validate_kwarg_propagates(tmp_path: Path) -> None:
    """compile_shards(validate=True) must route each scene through the retry path."""
    compiler = SceneCompiler(_make_config(), global_seed=42, output_dir=tmp_path)

    with patch.object(SceneCompiler, "compile_scene", wraps=compiler.compile_scene) as mocked:
        compiler.compile_shards(shard_index=0, total_shards=1, validate=True)

    assert mocked.call_count == 10
    for call in mocked.call_args_list:
        assert call.kwargs.get("validate") is True
