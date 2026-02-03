"""
Experiment Logic for render-tag.

Handles the expansion of high-level Experiment descriptions into concrete
variants (SceneRecipes) and manages provenance (Manifests).
"""

import json
import random
from pathlib import Path
from typing import Any

import numpy as np

from render_tag.config import GenConfig

from .experiment_schema import Experiment, ExperimentVariant, Sweep, SweepType


def seed_everything(seed: int):
    """Set seeds for all RNGs to ensure reproducibility.

    Args:
        seed: The integer seed to use.
    """
    random.seed(seed)
    np.random.seed(seed)


def load_experiment_config(path: Path) -> Experiment:
    """Load and validate an experiment configuration file."""
    import yaml

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}

    # Check if this is an experiment or regular config
    if "base_config" not in data:
        raise ValueError("Experiment config must contain 'base_config'")

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
            ) from e

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


def save_manifest(output_dir: Path, variant: ExperimentVariant, cli_args: list[str] | None = None):
    """Save a provenance manifest for a generated dataset."""
    import datetime
    import subprocess

    # Get Git SHA
    try:
        git_sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError:
        git_sha = "unknown"

    manifest = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "git_sha": git_sha,
        "command": " ".join(cli_args) if cli_args else "unknown",
        "experiment_name": variant.experiment_name,
        "variant_id": variant.variant_id,
        "description": variant.description,
        "overrides": variant.overrides,
        "config": variant.config.model_dump(mode="json"),
        "seed_info": {
            "global": variant.config.dataset.seeds.global_seed,
            "layout": variant.config.dataset.seeds.layout_seed,
            "lighting": variant.config.dataset.seeds.lighting_seed,
            "camera": variant.config.dataset.seeds.camera_seed,
            "noise": variant.config.dataset.seeds.noise_seed,
        },
    }

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


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
