# Schema migrations and legacy shims

The Anti-Corruption Layer (`render_tag.core.schema_adapter.adapt_config`)
translates raw configuration dicts into dicts that match the current Pydantic
schema. It runs three sequential passes:

```
raw dict -> flat_to_nested -> migrations -> field_map -> adapted dict
```

Each pass has its own rules for when to add code and when to remove it.

## The three passes

### 1. `schema.legacy.flat_to_nested`

Pre-versioning configs stored every field at the top level
(`resolution`, `samples`, `tag_family`, ...). This pass rewrites that shape
into the nested sections (`dataset`, `camera`, `tag`, `scene`, `scenario`).
It is a **one-shot historical shim** — no new fields are added here. Runs
first because the migration chain downstream assumes the nested shape.

### 2. `schema.migrations`

The versioned migration chain. Each hop is a module under
`src/render_tag/core/schema/migrations/` exposing:

```python
FROM_VERSION: str = "0.1"
TO_VERSION: str = "0.2"

def apply(data: dict[str, Any]) -> dict[str, Any]: ...
```

The package `__init__` discovers these modules, builds a `REGISTRY`, and
validates at import time that the chain is gap-free from `"0.0"` to
`CURRENT_SCHEMA_VERSION`. A missing hop raises `ImportError` at startup.

**The one-way-door rule.** Never edit a migration module after it ships.
Configs produced by earlier pipeline versions already exist on disk and in
CI artifacts. They must continue to migrate exactly as they did when they
were written. To change a migration's *effect*, add a later hop — don't
rewrite history.

### 3. `schema.legacy.field_map`

A declarative table of deprecated-field rewrites that don't warrant a
version bump. Each entry in `LEGACY_FIELDS` carries:

- `path` — dotted identifier of the legacy field.
- `replacement` — dotted identifier of the replacement.
- `since` — package version (from `pyproject.toml`) where the deprecation
  was first surfaced.
- `removed_in` — package version where the entry must be gone.
- `apply(data)` — function that mutates `data` in place, emitting a
  `DeprecationWarning` when the legacy field is encountered.

**Sunset enforcement.** `tests/unit/core_logic/test_legacy_sunset.py`
compares each entry's `removed_in` against the current package version.
When the deadline passes, the build fails. The intended response is to
delete the entry, not extend the deadline.

## Ordering matters

The three passes are **not commutative**. Each one assumes the output shape
of the previous:

- The migrator reads nested `tag.*` and `scenario.*`; it would silently
  no-op on a flat dict.
- The field map strips fields that the migrator needs in order to synthesize
  `scenario.subject`.

`tests/unit/test_schema_adapter.py::test_order_dependence_*` pins this
invariant down. If a refactor ever reorders the passes, those tests fail.

## How to add a versioned migration

1. Create a new module `schema/migrations/v{from}_to_v{to}.py` with
   `FROM_VERSION`, `TO_VERSION`, and `apply(data) -> data`.
2. Bump `render_tag.core.constants.CURRENT_SCHEMA_VERSION` to the new `to`.
3. Add a golden fixture pair under `schema/migrations/fixtures/` — at minimum
   a primary case, and edge cases for anything non-trivial. The
   `test_migration_golden` parametrized test auto-discovers them.
4. Run the suite. The registry is validated at import time, so a missing
   hop or name mismatch fails fast.

No edits to `schema_adapter.py` or the registry are required — discovery
is automatic.

## How to add a legacy field map entry

1. Append a `LegacyEntry(...)` to `LEGACY_FIELDS` in
   `schema/legacy/field_map.py`.
2. If the rewrite is non-trivial, add a helper function in the same module
   and reference it as the `apply` callable.
3. Pick `since` (current package version) and `removed_in` (typically the
   next major — see existing entries for convention).
4. Add a regression test exercising the new path.

## When to use which

| Symptom | Mechanism |
|---|---|
| Schema shape changed (new/renamed section; new required field) | Versioned migration |
| Field renamed or unit-converted without changing the version | Field map |
| Configs from a pipeline version before today need rescuing | Versioned migration |
| Old field name should warn and disappear on a schedule | Field map |

If you're not sure: write it as a migration. The one-way-door rule makes
migrations more durable; field-map entries are meant to disappear.

## Related files

- `src/render_tag/core/schema_adapter.py` — the public entry point.
- `src/render_tag/core/schema/migrations/` — versioned migrations + goldens.
- `src/render_tag/core/schema/legacy/flat_to_nested.py` — historical shim.
- `src/render_tag/core/schema/legacy/field_map.py` — declarative sunset
  table.
- `tests/unit/test_schema_adapter.py` — end-to-end + order-dependence.
- `tests/unit/core_logic/core/test_migration_goldens.py` — fixture-driven.
- `tests/unit/core_logic/test_legacy_sunset.py` — deadline enforcement.
