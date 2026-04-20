"""Golden-fixture tests for the versioned migration chain.

Each subdirectory under ``schema/migrations/fixtures/`` holds a ``before.yaml``
and ``after.yaml`` pair. The directory name encodes the migration to apply:

    v0_0_to_v0_1/                 -> v0_0_to_v0_1.apply
    v0_1_to_v0_2_tags/            -> v0_1_to_v0_2.apply
    v0_1_to_v0_2_board/           -> v0_1_to_v0_2.apply
    v0_1_to_v0_2_tag_section_only -> v0_1_to_v0_2.apply

A fixture directory whose name starts with ``v{X}_{Y}_to_v{A}_{B}`` is routed
to the module ``v{X}_{Y}_to_v{A}_{B}.apply``; any suffix (``_tags``,
``_board``, ...) distinguishes cases without demanding a separate module.
"""

from __future__ import annotations

import importlib
import re
import warnings
from pathlib import Path

import pytest
import yaml

import render_tag.core.schema.migrations as _migrations_pkg

FIXTURES_ROOT = Path(_migrations_pkg.__file__).resolve().parent / "fixtures"

_MODULE_RE = re.compile(r"^(v\d+_\d+_to_v\d+_\d+)")


def _discover_fixtures() -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    if not FIXTURES_ROOT.exists():
        return pairs
    for fixture_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not fixture_dir.is_dir():
            continue
        if not (fixture_dir / "before.yaml").exists():
            continue
        match = _MODULE_RE.match(fixture_dir.name)
        assert match, (
            f"Fixture dir {fixture_dir.name!r} must start with v{{X}}_{{Y}}_to_v{{A}}_{{B}}"
        )
        pairs.append((match.group(1), fixture_dir))
    return pairs


@pytest.mark.parametrize("module_name,fixture_dir", _discover_fixtures())
def test_migration_golden(module_name: str, fixture_dir: Path):
    """module.apply(before) must equal after for every fixture pair."""
    module = importlib.import_module(f"render_tag.core.schema.migrations.{module_name}")
    before = yaml.safe_load((fixture_dir / "before.yaml").read_text())
    after = yaml.safe_load((fixture_dir / "after.yaml").read_text())

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = module.apply(before)

    assert result == after, (
        f"Migration {module_name} diverged from golden for {fixture_dir.name!r}.\n"
        f"Expected: {after}\nActual:   {result}"
    )
