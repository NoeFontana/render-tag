"""
Experiment Logic for render-tag.

Handles the expansion of high-level Experiment descriptions into concrete
variants (SceneRecipes) and manages provenance (Manifests).
"""

import random
from pathlib import Path
from typing import Any

import numpy as np

from render_tag.core.config import GenConfig

from .experiment_schema import (
    Campaign,
    Experiment,
    ExperimentVariant,
    Sweep,
    SweepType,
)


def seed_everything(seed: int):
    """Set seeds for all RNGs to ensure reproducibility.

    Args:
        seed: The integer seed to use.
    """
    random.seed(seed)
    np.random.seed(seed)


def load_experiment_config(path: Path) -> Experiment | Campaign:
    """Load and validate an experiment configuration file."""
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}

    # Check if this is a Campaign (has 'experiments' key)
    if "experiments" in data:
        return Campaign(**data)

    # Check if this is an experiment or regular config
    if "base_config" not in data:
        raise ValueError("Experiment config must contain 'base_config' or 'experiments'")

    # Validation happens here via Pydantic
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
    """Expand a Campaign into a list of concrete Variants."""
    import yaml

    variants = []

    base_output_dir = Path(campaign.output_dir)

    for sub_exp in campaign.experiments:
        # Load the preset config
        config_path = Path(sub_exp.config_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config for sub-experiment '{sub_exp.name}' not found at {config_path}"
            )

        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

        # Apply overrides
        # We can use the same logic as _update_nested_dict but we need to
        # iterate over the overrides dict
        def _apply_overrides_recursive(d, overrides_dict, prefix=""):
            for k, v in overrides_dict.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    _apply_overrides_recursive(d[k], v, prefix + k + ".")
                else:
                    # Flat override or leaf node
                    d[k] = v

        # Simple recursive merge isn't enough because overrides might be flat dot notation
        # or nested dict. Let's assume nested dict structure matches config structure
        # based on how we wrote the yaml.

        # Actually, let's use a merge utility.
        # But wait, expand_experiment uses dot notation for sweeps.
        # In the campaign yaml, overrides are nested dictionaries.

        def deep_merge(target, source):
            for key, value in source.items():
                if isinstance(value, dict):
                    node = target.setdefault(key, {})
                    deep_merge(node, value)
                else:
                    target[key] = value

        deep_merge(config_data, sub_exp.overrides)

        # Inject campaign-level metadata
        if campaign.metadata:
            if "dataset" not in config_data:
                config_data["dataset"] = {}
            if "metadata" not in config_data["dataset"]:
                config_data["dataset"]["metadata"] = {}
            config_data["dataset"]["metadata"].update(campaign.metadata)

        try:
            config = GenConfig.model_validate(config_data)
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


def _update_nested_dict(d: dict[str, Any], path: str, value: Any):
    """Update a nested dictionary using dot-notation path."""
    parts = path.split(".")
    curr = d
    for part in parts[:-1]:
        if part not in curr:
            curr[part] = {}
        curr = curr[part]
        if not isinstance(curr, dict):
            # If we hit a Pydantic model dump that is a list or other type,
            # we can't recurse easily with dot notation unless we support list indexing
            # e.g. "cameras.0.fov"
            raise ValueError(f"Cannot traverse path '{path}' at '{part}': not a dict")

    curr[parts[-1]] = value


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
