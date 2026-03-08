"""
Finalization stage for the generation pipeline.
Handles manifest generation and checksums.
"""

import hashlib
import sys
from pathlib import Path

from render_tag.audit.reporting import generate_dataset_info
from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import console, get_asset_manager
from render_tag.core.manifest import ChecksumManifest
from render_tag.core.schema.job import (
    JobPaths,
    JobSpec,
    calculate_job_id,
    get_env_fingerprint,
)
from render_tag.data_io.writers import (
    merge_coco_shards,
    merge_csv_shards,
    merge_provenance_shards,
    merge_rich_truth_shards,
)


class FinalizationStage(PipelineStage):
    """Generates final metadata and checksums for the dataset."""

    def execute(self, ctx: GenerationContext) -> None:
        if not ctx.gen_config:
            return

        # 1. Merge Shards
        self._merge_shards(ctx.output_dir)

        console.print("\n[bold blue]Generating dataset metadata...[/bold blue]")

        if ctx.job_spec:
            ctx.final_job_id = calculate_job_id(ctx.job_spec)
        else:
            ctx.final_job_id = self._create_virtual_job_id(ctx)

        # 2. Unified Metadata
        generate_dataset_info(
            dataset_dir=ctx.output_dir,
            config=ctx.gen_config,
            cli_args=sys.argv,
        )

        # 3. Checksums
        manifest = ChecksumManifest(job_id=ctx.final_job_id, output_dir=ctx.output_dir)
        manifest.add_directory(ctx.output_dir / "images", pattern="*.png")
        for filename in [
            "ground_truth.csv",
            "coco_labels.json",
            "rich_truth.json",
            "provenance.json",
        ]:
            path = ctx.output_dir / filename
            if path.exists():
                manifest.add_file(path)

        path = manifest.save()
        console.print(f"[dim]Checksums saved to:[/dim] {path}")
        console.print("[bold green]✓ Generation session complete[/bold green]")

    def _merge_shards(self, output_dir: Path) -> None:
        """Merge shard-specific CSV and JSON files into unified outputs."""
        console.print("[dim]Merging dataset shards...[/dim]")
        # CSV Shards
        merge_csv_shards(output_dir, final_filename="ground_truth.csv", cleanup=True)
        # COCO Shards
        merge_coco_shards(output_dir, final_filename="coco_labels.json", cleanup=True)
        # RichTruth Shards
        merge_rich_truth_shards(output_dir, final_filename="rich_truth.json", cleanup=True)
        # Provenance Shards
        merge_provenance_shards(output_dir, final_filename="provenance.json", cleanup=True)

    def _create_virtual_job_id(self, ctx: GenerationContext) -> str:
        if not ctx.gen_config:
            return "unknown"

        am = get_asset_manager()
        env_hash, blender_ver = get_env_fingerprint()

        cfg_hash = "unknown"
        if ctx.config_path and ctx.config_path.exists():
            with open(ctx.config_path, "rb") as f:
                cfg_hash = hashlib.sha256(f.read()).hexdigest()

        paths = JobPaths(
            output_dir=ctx.output_dir,
            logs_dir=ctx.output_dir / "logs",
            assets_dir=Path("assets"),
        )

        adhoc = JobSpec(
            job_id="adhoc",
            paths=paths,
            global_seed=ctx.seed,
            scene_config=ctx.gen_config,
            env_hash=env_hash,
            blender_version=blender_ver,
            assets_hash=am.get_assets_hash(),
            config_hash=cfg_hash,
            shard_index=ctx.shard_index,
        )
        return calculate_job_id(adhoc)
