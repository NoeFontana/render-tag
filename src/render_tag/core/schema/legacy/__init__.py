"""Legacy compatibility shims for the Anti-Corruption Layer.

Two kinds of shim live here:

- ``flat_to_nested``: a one-shot transform that predates schema versioning.
  Top-level fields (e.g. ``resolution``, ``seed``) are rewritten into their
  nested sections. Runs before the migration chain because the migrator
  assumes the nested shape.
- ``field_map``: a declarative table of deprecated field -> current field
  rewrites with explicit sunset metadata (``since`` / ``removed_in``). Runs
  after the migration chain to clean up residual legacy fields.

Prefer the migrations package for schema-shape changes; prefer field_map for
field renames that don't require a version bump.
"""

from render_tag.core.schema.legacy.flat_to_nested import (
    detect_and_convert as detect_and_convert,
)
from render_tag.core.schema.legacy.flat_to_nested import (
    is_flat as is_flat,
)
