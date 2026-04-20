from pathlib import Path
from typing import Any

import yaml

from render_tag.core.config import GenConfig
from render_tag.core.presets import append_cli_presets
from render_tag.core.schema.job import (
    JobInfrastructure,
    JobPaths,
    JobSpec,
    get_env_fingerprint,
)
from render_tag.core.schema_adapter import adapt_config


class ConfigResolver:
    """Resolves raw configuration into an immutable JobSpec."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path

    def resolve(
        self,
        output_dir: Path,
        overrides: dict[str, Any] | None = None,
        seed: int | str = "auto",
        shard_index: int = 0,
        scene_limit: int | None = None,
        cli_presets: list[str] | None = None,
    ) -> JobSpec:
        """
        Compiles the Final Job Spec.

        Args:
            output_dir: Root directory for job output (job_spec.json lives here)
            overrides: Dictionary of CLI overrides (e.g. {'dataset.num_scenes': 10})
            seed: Master seed or "auto"
            shard_index: The shard index for this job run
            scene_limit: Optional override for number of scenes (legacy CLI)
            cli_presets: Preset names from the CLI, appended after any YAML
                ``presets: [...]`` list so later entries win.

        Returns:
            Frozen JobSpec object.
        """
        # 1. Load Base Config — CLI presets, if any, are merged into the raw
        # dict before the ACL runs so composition order is preserved.
        gen_config = self._load_with_cli_presets(cli_presets)

        # 2. Apply Overrides
        if scene_limit is not None and scene_limit > 0:
            gen_config.dataset.num_scenes = scene_limit

        # Handle random seed
        final_seed = 0
        if seed == "auto":
            import random

            final_seed = random.randint(0, 2**32 - 1)
        else:
            final_seed = int(seed)

        # Override seed in config
        gen_config.dataset.seeds.global_seed = final_seed

        # Apply generic overrides (e.g. from CLI --set key=value)
        # This is a placeholder for future generic override logic
        if overrides:
            self._apply_overrides(gen_config, overrides)
            # Re-validate to ensure type coercion and validation
            # (e.g. string to float, list to tuple)
            gen_config = GenConfig.model_validate(gen_config.model_dump())

        # 3. Path Resolution (Absolute Paths)
        # We need to resolve all Path fields to absolute paths based on CWD
        # or relative to the config file?
        # Standard convention: Relative paths in config are relative to CWD where render-tag is run.
        self._resolve_paths(gen_config)

        # 4. Environment Fingerprinting
        env_hash, blender_ver = get_env_fingerprint()

        # 5. Job Identity
        # Ensure output_dir is absolute
        abs_output_dir = output_dir.resolve()

        # Create Job Paths
        job_paths = JobPaths(
            output_dir=abs_output_dir,
            logs_dir=abs_output_dir / "logs",
            assets_dir=Path("assets").resolve(),  # Mock default for now? Or use env var?
        )

        # Infrastructure Defaults
        infra = JobInfrastructure()

        # 6. Construct Spec
        # Job ID is calculated from the *content* of the spec (excluding ID/timestamp)
        # So we construct a temporary spec without ID?
        # JobSpec needs ID.
        # We can calculate ID from config + seed + environment.

        # Create a partial fingerprint for ID calculation
        spec_content = {
            "config": gen_config.model_dump(mode="json"),
            "env": env_hash,
            "seed": final_seed,
            "shard": shard_index,
        }
        import hashlib
        import json

        job_id_hash = hashlib.sha256(json.dumps(spec_content, sort_keys=True).encode()).hexdigest()
        job_id = f"job-{job_id_hash[:8]}"

        assets_hash = self._calculate_assets_hash(gen_config)

        spec = JobSpec(
            version="0.1",
            job_id=job_id,
            paths=job_paths,
            infrastructure=infra,
            global_seed=final_seed,
            scene_config=gen_config,
            env_hash=env_hash,
            blender_version=blender_ver,
            assets_hash=assets_hash,
            config_hash=hashlib.sha256(gen_config.model_dump_json().encode()).hexdigest(),
            shard_index=shard_index,
            applied_presets=list(gen_config.presets),
        )

        return spec

    def _load_with_cli_presets(self, cli_presets: list[str] | None) -> GenConfig:
        """Load YAML + append CLI presets + run ACL + validate.

        CLI presets are appended after any YAML ``presets: [...]`` list so
        later entries compose on top.
        """
        if self.config_path is None and not cli_presets:
            return GenConfig()
        if self.config_path is None:
            data: dict[str, Any] = {}
        else:
            with open(self.config_path) as f:
                data = yaml.safe_load(f) or {}
        append_cli_presets(data, cli_presets)
        return GenConfig.model_validate(adapt_config(data))

    def _calculate_assets_hash(self, config: GenConfig) -> str:
        """Calculate a hash of all assets referenced in the configuration."""
        import hashlib

        hasher = hashlib.sha256()

        def hash_path(path: Path | None) -> None:
            if path is None:
                hasher.update(b"none")
                return

            if path.exists():
                if path.is_file():
                    with open(path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hasher.update(chunk)
                elif path.is_dir():
                    # Hash all files in directory, sorted by name
                    for p in sorted(path.rglob("*")):
                        if p.is_file():
                            hasher.update(str(p.relative_to(path)).encode())
                            with open(p, "rb") as f:
                                for chunk in iter(lambda: f.read(4096), b""):
                                    hasher.update(chunk)
            else:
                hasher.update(f"missing:{path}".encode())

        # 1. HDRI
        hash_path(config.scene.background_hdri)

        # 2. Textures (Directory)
        hash_path(config.scene.texture_dir)

        # 3. Tag Texture
        hash_path(config.tag.texture_path)

        return hasher.hexdigest()

    def _apply_overrides(self, config: GenConfig, overrides: dict[str, Any]) -> None:
        """Apply CLI overrides to the configuration."""
        if not overrides:
            return

        # Special handling for renderer mode
        if "renderer_mode" in overrides:
            config.renderer.mode = overrides["renderer_mode"]

        # Implement generic dot-notation overrides
        # e.g. overrides={"camera.fov": 90.0, "scenario.tag_families.0": "tag16h5"}
        for path, value in overrides.items():
            if path == "renderer_mode":
                continue

            # Intercept resolution override to scale intrinsics correctly
            if path == "camera.resolution":
                # Value should be like [1920, 1080] or (1920, 1080)
                # It might come as a string like "[1920, 1080]" from CLI
                if isinstance(value, str):
                    import ast

                    try:
                        res = ast.literal_eval(value)
                        if isinstance(res, (list, tuple)) and len(res) == 2:
                            config.camera.scale_resolution(res[0], res[1])
                            continue
                    except Exception:
                        pass
                elif isinstance(value, (list, tuple)) and len(value) == 2:
                    config.camera.scale_resolution(value[0], value[1])
                    continue

            parts = path.split(".")
            target: Any = config
            for _i, part in enumerate(parts[:-1]):
                if part.isdigit():
                    target = target[int(part)]  # type: ignore[index]
                elif hasattr(target, part):
                    target = getattr(target, part)
                elif isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    raise AttributeError(f"Invalid config path: {path} (at {part})")

            last_part = parts[-1]
            if last_part.isdigit():
                idx = int(last_part)
                target[idx] = value  # type: ignore[index]
            elif hasattr(target, last_part):
                setattr(target, last_part, value)
            elif isinstance(target, dict):
                target[last_part] = value
            else:
                raise AttributeError(f"Invalid config path: {path} (at {last_part})")

    def _resolve_paths(self, config: GenConfig) -> None:
        """recursively find Path objects and make them absolute."""
        # This is tricky because Pydantic models are nested.
        # Simple approach: Explicitly handle known paths.

        # Dataset
        if not config.dataset.output_dir.is_absolute():
            config.dataset.output_dir = config.dataset.output_dir.resolve()

        # Scene
        if config.scene.background_hdri and not config.scene.background_hdri.is_absolute():
            config.scene.background_hdri = config.scene.background_hdri.resolve()
        if config.scene.texture_dir and not config.scene.texture_dir.is_absolute():
            config.scene.texture_dir = config.scene.texture_dir.resolve()

        # Tag
        if config.tag.texture_path and not config.tag.texture_path.is_absolute():
            config.tag.texture_path = config.tag.texture_path.resolve()
