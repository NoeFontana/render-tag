# tests/

## Blender mocking invariant

`bpy`, `blenderproc`, and `mathutils` must be installed in `sys.modules`
**before** any `render_tag.backend.*` import runs. Many backend modules import
these at module top-level, and Python has no hook for "substitute this module
if it can't be found."

The invariant is enforced by `tests/_plugins/blender_mocks/plugin.py`, which
runs `_inject_blender_mocks()` at module-import time. The plugin is registered
via the `pytest_plugins` variable in `tests/conftest.py`; pytest imports listed
plugins during startup, before test collection begins.

Any future change to test bootstrap must preserve this ordering. If you're
tempted to move the injection into `pytest_configure` or later — don't. Pytest's
collection phase imports test modules before those hooks fire.

The sanity tests in `tests/_plugins/blender_mocks/test_plugin.py` assert the
mocks are actually in `sys.modules`. If the plugin stops loading, those tests
fail loudly instead of producing confusing errors deep in downstream tests.

## Test tiers

- `tests/unit/core_logic/` — pure-logic tests, no mocks beyond stdlib, no
  subprocess calls, no fixtures that touch Blender.
- `tests/unit/heavy_logic/` — logic that touches Blender mocks, patches
  subprocess, or uses non-trivial fixtures. Runs without spawning processes.
- `tests/integration/` — shells out to `uv run`, spawns worker processes,
  or otherwise exercises end-to-end behavior. Every test in this directory
  is automatically treated as `integration` (the plugin tags them during
  collection).
- `tests/verification/` — one-off verification scripts (not routinely run).

A handful of tests outside `tests/integration/` are also marked
`@pytest.mark.integration` because they spawn real processes — e.g.
`tests/unit/heavy_logic/orchestration/test_stability_patterns.py` and
`tests/unit/core_logic/core/test_import_linter_contracts.py`.

## How to invoke

- Fast loop: `uv run pytest -m "not integration"`
- Full suite: `uv run pytest`
- Single tier: `uv run pytest tests/unit/core_logic`
- Single file: `uv run pytest tests/unit/heavy_logic/cli/test_cli_viz.py`

`addopts = "-n 4 --dist loadfile"` in `pyproject.toml` runs the suite under
pytest-xdist by default. Integration tests are auto-grouped onto a single
worker via `xdist_group(name="serial_integration")` to avoid memory
exhaustion from parallel Blender/subprocess instances.

## Marker enforcement

Tests that call `subprocess.run`, `subprocess.Popen`, `subprocess.call`,
`subprocess.check_call`, or `subprocess.check_output` **must** carry the
`integration` marker (either via `@pytest.mark.integration`, a file-level
`pytestmark`, or by living under `tests/integration/`).

The plugin rejects unmarked subprocess callers at collection time with a
clear error listing the offenders. Tests that *patch* subprocess — via
`mock.patch("subprocess.run")`, `patch.object(subprocess, "run")`, or
`monkeypatch.setattr(subprocess, "run", ...)` — are accepted as unit tests
because they never spawn a real child.

If the enforcement flags a test that shouldn't be an integration test,
the fix is usually to switch from direct subprocess calls to one of the
patching patterns above.

## Future work

`tests/_plugins/blender_mocks/` is structured to be extractable as a
standalone package (e.g. `pytest-blender-mocks`) if another repo in the
org ever grows the same need. No work planned — flagged here so the option
isn't forgotten.
