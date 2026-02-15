from pathlib import Path
from typing import Any

from render_tag.core.config import GenConfig, load_config
from render_tag.core.schema.job import (
    JobInfrastructure,
    JobPaths,
    JobSpec,
    get_env_fingerprint,
)


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
    ) -> JobSpec:
        """
        Compiles the Final Job Spec.

        Args:
            output_dir: Root directory for job output (job_spec.json lives here)
            overrides: Dictionary of CLI overrides (e.g. {'dataset.num_scenes': 10})
            seed: Master seed or "auto"
            shard_index: The shard index for this job run
            scene_limit: Optional override for number of scenes (legacy CLI)

        Returns:
            Frozen JobSpec object.
        """
        # 1. Load Base Config
        if self.config_path:
            # We use safe_load directly to get a dict first, to apply overrides easily
            # But load_config handles legacy flat config...
            # Let's use load_config to get a clean object, then dump to dict if needed,
            # OR just modify the object.
            # Modifying the object is cleaner if we can set attributes.
            # But Pydantic models might be immutable or validated.
            # GenConfig is not frozen by default.
            gen_config = load_config(self.config_path)
        else:
            # Default config if none provided?
            # Or raise error?
            # Typically existing flow allows default.
            gen_config = GenConfig()

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

        spec = JobSpec(
            version="1.0",
            job_id=job_id,
            paths=job_paths,
            infrastructure=infra,
            global_seed=final_seed,
            scene_config=gen_config,
            env_hash=env_hash,
            blender_version=blender_ver,
            assets_hash="unknown",  # TODO: Implement asset hashing
            config_hash=hashlib.sha256(gen_config.model_dump_json().encode()).hexdigest(),
            shard_index=shard_index,
        )

        return spec

    def _apply_overrides(self, config: GenConfig, overrides: dict[str, Any]) -> None:
        """Apply CLI overrides to the configuration."""
        if not overrides:
            return

        # Special handling for renderer mode
        if "renderer_mode" in overrides:
            config.renderer.mode = overrides["renderer_mode"]

        # TODO: Implement generic dot-notation overrides if needed
        # e.g. overrides={"scene.lighting.intensity": 50}

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
