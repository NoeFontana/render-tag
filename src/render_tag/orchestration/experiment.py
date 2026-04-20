"""
Experiment Logic for render-tag.

Handles the expansion of high-level Experiment descriptions into concrete
variants (SceneRecipes) and manages provenance (Manifests).
"""

import copy
import itertools
from pathlib import Path
from typing import Any

import numpy as np

from render_tag.core.config import GenConfig

from .experiment_schema import (
    Campaign,
    CampaignMatrix,
    Experiment,
    ExperimentVariant,
    SubExperiment,
    Sweep,
    SweepType,
)


def load_experiment_config(path: Path) -> Experiment | Campaign:
    """Load and validate an experiment configuration file."""
    import yaml

    from render_tag.core.schema_adapter import adapt_config

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}

    # Check if this is a Campaign (has 'experiments' or 'matrices' key)
    if "experiments" in data or "matrices" in data:
        return Campaign(**data)

    # Check if this is an experiment or regular config
    if "base_config" not in data:
        raise ValueError(
            "Experiment config must contain 'base_config', 'experiments', or 'matrices'"
        )

    # Run the ACL on base_config so legacy-field rewrites, migrations, and
    # `presets: [...]` expansion apply to experiments the same way they do
    # to standalone configs. Without this, a ``presets:`` list inside
    # base_config would slip through unexpanded and the experiment would
    # silently run with bare schema defaults for preset-supplied fields.
    data["base_config"] = adapt_config(data["base_config"])

    return Experiment(**data)


def expand_experiment(experiment: Experiment) -> list[ExperimentVariant]:
    """Expand an Experiment into a list of concrete Variants.

    This performs a parameter sweep (grid search) across all defined sweeps.
    """
    if not experiment.sweeps:
        # Single variant (Base)
        return [
            ExperimentVariant(
                experiment_name=experiment.name,
                variant_id="base",
                description="Base configuration",
                config=experiment.base_config,
                overrides={},
            )
        ]

    # Generate all combinations of parameters
    import itertools

    sweep_values = []
    sweep_names = []

    for sweep in experiment.sweeps:
        sweep_names.append(sweep.parameter)
        sweep_values.append(_get_sweep_values(sweep))

    # itertools.product gives us the cartesian product
    combinations = list(itertools.product(*sweep_values))

    variants = []
    for i, combo in enumerate(combinations):
        variant_id = f"v{i:03d}"
        overrides = {}
        description_parts = []

        # Deep copy base config
        # We start with model_dump to get a dict, update it, then re-validate
        config_dict = experiment.base_config.model_dump()

        for sweep_idx, val in enumerate(combo):
            param = sweep_names[sweep_idx]
            overrides[param] = val
            description_parts.append(f"{param}={val}")

            # Update config dict
            _update_nested_dict(config_dict, param, val)

        # Handle Seeding / Locking Logic
        # If a lock is enabled, we use the base config's seed for that aspect.
        # If disabled, we might want to vary it per variant to simulate independent trials.
        # However, typically "disabled lock" means "I care about this variance", but usually
        # in the context of controlled experiments, we WANT locks.
        # If someone sweeps "noise_seed", they are explicitly varying it.
        # If 'lock_camera' is False, should we change the camera seed?
        # A common pattern: Base seed + Variant Index if NOT locked.

        base_seeds = config_dict.get("dataset", {}).get("seeds", {})
        # Ensure it exists if flat config was normalized differently
        # (handled by schema but dict might vary)
        if "seeds" not in config_dict.get("dataset", {}):
            config_dict.setdefault("dataset", {})["seeds"] = {}

        global_seed = base_seeds.get("global_seed", 42)

        # We need to set explicit overrides in SeedConfig if they aren't locked
        # If they ARE locked, we don't need to touch them.
        # BUT if we change global_seed, everything changes.
        # So we usually keep global_seed constant but utilize the granular seeds.

        seeds_update = {}

        if not experiment.lock_layout:
            # Vary layout per variant
            seeds_update["layout"] = global_seed + i * 100
        elif "layout" not in base_seeds:
            # Explicitly lock it to global seed to be safe?
            # No, SeedConfig defaults layout->global.
            # So as long as global doesn't change we are good.
            pass

        if not experiment.lock_lighting:
            seeds_update["lighting"] = global_seed + i * 200

        if not experiment.lock_camera:
            seeds_update["camera"] = global_seed + i * 300

        # Apply seed updates
        config_dict["dataset"]["seeds"].update(seeds_update)

        # Re-validate
        try:
            new_config = GenConfig.model_validate(config_dict)
        except Exception as e:
            raise ValueError(
                f"Failed to create config for {variant_id} with {overrides}: {e}"
            ) from None

        variants.append(
            ExperimentVariant(
                experiment_name=experiment.name,
                variant_id=variant_id,
                description=", ".join(description_parts),
                config=new_config,
                overrides=overrides,
            )
        )

    return variants


def expand_campaign(campaign: Campaign) -> list[ExperimentVariant]:
    """Expand a Campaign into a list of concrete Variants.

    Processes explicitly-enumerated ``experiments`` first, then expands each
    ``matrices`` entry Cartesian-style into additional SubExperiments before
    running them through the same loader path.
    """
    import yaml

    from render_tag.core.merge import deep_merge
    from render_tag.core.schema_adapter import adapt_config

    variants = []

    base_output_dir = Path(campaign.output_dir)

    all_sub_exps: list[SubExperiment] = list(campaign.experiments)
    for matrix in campaign.matrices:
        all_sub_exps.extend(_expand_matrix(matrix))

    # Matrix expansion produces many variants pointing at the same source YAML
    # (e.g. one YAML x N resolutions). Parse each YAML once; `deep_merge`
    # deep-copies the cached target on every call so the source stays pristine.
    raw_cache: dict[Path, dict[str, Any]] = {}

    for sub_exp in all_sub_exps:
        config_path = Path(sub_exp.config_path)
        if config_path not in raw_cache:
            try:
                with open(config_path) as f:
                    raw_cache[config_path] = yaml.safe_load(f) or {}
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Config for sub-experiment '{sub_exp.name}' not found at {config_path}"
                ) from e

        config_data = deep_merge(raw_cache[config_path], sub_exp.overrides)

        # Inject campaign-level metadata
        if campaign.metadata:
            if "dataset" not in config_data:
                config_data["dataset"] = {}
            if "metadata" not in config_data["dataset"]:
                config_data["dataset"]["metadata"] = {}
            config_data["dataset"]["metadata"].update(campaign.metadata)

        try:
            config = GenConfig.model_validate(adapt_config(config_data))
        except Exception as e:
            raise ValueError(f"Invalid config for sub-experiment '{sub_exp.name}': {e}") from e

        # Set explicit output directory for this variant
        # structure: <campaign_output>/<sub_exp_name>
        variant_output_dir = base_output_dir / sub_exp.name
        config.dataset.output_dir = variant_output_dir

        # We create a single variant per sub-experiment
        # (Campaigns don't sweep yet, they just orchestrate)
        variant = ExperimentVariant(
            experiment_name=sub_exp.name,
            variant_id="main",  # Single variant
            description=f"Campaign sub-experiment: {sub_exp.name}",
            config=config,
            overrides=sub_exp.overrides,
        )
        variants.append(variant)

    return variants


def _get_sweep_values(sweep: Sweep) -> list[Any]:
    if sweep.type == SweepType.CATEGORICAL:
        return sweep.values or []
    elif sweep.type == SweepType.LINEAR:
        # Generate linear range
        assert sweep.min is not None
        assert sweep.max is not None
        if sweep.step:
            # arange may handle floats poorly, careful
            # Use linspace style logic if possible or exact steps
            values = []
            curr = sweep.min
            while curr <= sweep.max + 1e-9:
                values.append(curr)
                if sweep.step is not None:
                    curr += sweep.step
                else:
                    break
            return values
        elif sweep.steps is not None:
            assert sweep.min is not None
            assert sweep.max is not None
            return list(np.linspace(sweep.min, sweep.max, sweep.steps))
    return []


def _expand_matrix(matrix: CampaignMatrix) -> list[SubExperiment]:
    """Cartesian-expand a ``CampaignMatrix`` into concrete SubExperiments.

    The base SubExperiment's fixed ``overrides`` apply to every variant; each
    axis contributes one dotted ``parameter`` which is written into a fresh
    per-variant ``overrides`` dict (as a nested tree). Variant names suffix
    the base name with ``__{axis_slug}`` joined for multi-axis matrices.
    """
    axes = matrix.axes
    combos = list(itertools.product(*(axis.values for axis in axes)))

    sub_exps: list[SubExperiment] = []
    for combo in combos:
        slug_parts = [
            f"{_param_slug(axis.parameter)}-{_value_slug(value)}"
            for axis, value in zip(axes, combo, strict=True)
        ]
        variant_name = f"{matrix.base.name}__{'__'.join(slug_parts)}"

        overrides: dict[str, Any] = copy.deepcopy(matrix.base.overrides)
        for axis, value in zip(axes, combo, strict=True):
            _update_nested_dict(overrides, axis.parameter, value)

        sub_exps.append(
            SubExperiment.model_validate(
                {
                    "name": variant_name,
                    "config": matrix.base.config_path,
                    "overrides": overrides,
                }
            )
        )

    return sub_exps


def _param_slug(parameter: str) -> str:
    """Slugify a dotted config path for use in a variant name."""
    return parameter.replace(".", "_")


def _value_slug(value: Any) -> str:
    """Slugify a scalar or short list for use in a variant name."""
    if isinstance(value, list):
        return "x".join(_value_slug(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace(".", "p").replace("/", "_").replace(" ", "_")


def _update_nested_dict(d: dict[str, Any], path: str, value: Any):
    """Update a nested dictionary using dot-notation path.

    Numeric parts index into lists (e.g. ``scene.lighting.directional.0.azimuth``).
    """
    parts = path.split(".")
    curr: Any = d
    for part in parts[:-1]:
        if isinstance(curr, list):
            curr = curr[int(part)]
        elif isinstance(curr, dict):
            if part not in curr:
                curr[part] = {}
            curr = curr[part]
        else:
            raise ValueError(f"Cannot traverse path '{path}' at '{part}': not a dict or list")

    last = parts[-1]
    if isinstance(curr, list):
        curr[int(last)] = value
    else:
        curr[last] = value


def save_manifest(output_dir: Path, variant: ExperimentVariant, cli_args: list[str] | None = None):
    """Save an experiment variant manifest to JSON."""
    from render_tag.audit.reporting import generate_dataset_info

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use the centralized manifest generation
    generate_dataset_info(
        dataset_dir=output_dir,
        config=variant.config,
        experiment_info={
            "name": variant.experiment_name,
            "variant_id": variant.variant_id,
            "description": variant.description,
            "overrides": variant.overrides,
        },
        cli_args=cli_args,
    )
