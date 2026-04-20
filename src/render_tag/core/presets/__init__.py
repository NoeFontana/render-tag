"""First-class preset composition for render-tag configs.

Presets are named partial overrides composed left-to-right by the ACL's
preset-expansion pass (``pipeline.expand``). Users declare them via
``presets: [...]`` at the YAML top level or ``--preset NAME`` on the CLI.

Registration happens on import via ``@register_preset``; the side-effect
imports below ensure every built-in preset is available whenever this
package is loaded.
"""

from __future__ import annotations

from render_tag.core.presets.base import (
    Preset as Preset,
)
from render_tag.core.presets.base import (
    PresetRegistry as PresetRegistry,
)
from render_tag.core.presets.base import (
    default_registry as default_registry,
)
from render_tag.core.presets.base import (
    register_preset as register_preset,
)
from render_tag.core.presets.pipeline import (
    append_cli_presets as append_cli_presets,
)
from render_tag.core.presets.pipeline import (
    expand as expand,
)

# Side-effect imports — each module registers exactly one preset.
from . import (  # noqa: F401  (auto-registration on import)
    evaluation_calibration_full,
    lighting_factory,
    lighting_outdoor_industrial,
    lighting_warehouse,
    sensor_hdr_sweep,
    sensor_industrial_dr,
    sensor_raw_pipeline,
    shadow_harsh,
)

__all__ = [
    "Preset",
    "PresetRegistry",
    "append_cli_presets",
    "default_registry",
    "expand",
    "register_preset",
]
