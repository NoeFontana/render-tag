"""
Manifest generation stage.
"""

import hashlib
import sys

from rich.console import Console

from render_tag.audit.dataset_info import generate_dataset_info
from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import get_asset_manager
from render_tag.common.manifest import ChecksumManifest
from render_tag.schema.job import JobSpec, calculate_job_id, get_env_fingerprint

console = Console()


class ManifestGenerationStage(PipelineStage):
    """Generates dataset metadata and provenance manifests."""

    def execute(self, ctx: GenerationContext) -> None:
        if not ctx.gen_config:
            return

        console.print("\n[bold blue]Generating dataset metadata...[/bold blue]")

        if ctx.job_spec:
            ctx.final_job_id = calculate_job_id(ctx.job_spec)
        else:
            ctx._virtual_job_id = self._create_virtual_job_id(ctx)
            ctx.final_job_id = ctx._virtual_job_id

        # 1. Unified Metadata
        generate_dataset_info(
            dataset_dir=ctx.output_dir,
            config=ctx.gen_config,
            cli_args=sys.argv,
        )

        # 2. Checksums
        manifest = ChecksumManifest(job_id=ctx.final_job_id, output_dir=ctx.output_dir)
        manifest.add_directory(ctx.output_dir / "images", pattern="*.png")
        if (ctx.output_dir / "tags.csv").exists():
            manifest.add_file(ctx.output_dir / "tags.csv")
        if (ctx.output_dir / "annotations.json").exists():
            manifest.add_file(ctx.output_dir / "annotations.json")

        path = manifest.save()
        console.print(f"[dim]Checksums saved to:[/dim] {path}")
        console.print("[bold green]✓ Generation session complete[/bold green]")

    def _create_virtual_job_id(self, ctx: GenerationContext) -> str:
        am = get_asset_manager()
        env_hash, blender_ver = get_env_fingerprint()

        with open(ctx.config_path, "rb") as f:
            cfg_hash = hashlib.sha256(f.read()).hexdigest()

        adhoc = JobSpec(
            env_hash=env_hash,
            blender_version=blender_ver,
            assets_hash=am.get_assets_hash(),
            config_hash=cfg_hash,
            seed=ctx.seed,
            shard_index=ctx.shard_index,
            shard_size=ctx.num_scenes,
        )
        return calculate_job_id(adhoc)
