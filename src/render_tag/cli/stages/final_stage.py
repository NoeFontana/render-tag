"""
Finalization stage for the generation pipeline.
Handles manifest generation and checksums.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from rich.console import Console

from render_tag.audit.reporting import generate_dataset_info
from render_tag.cli.pipeline import GenerationContext, PipelineStage
from render_tag.cli.tools import get_asset_manager
from render_tag.core.manifest import ChecksumManifest
from render_tag.core.schema.job import JobSpec, calculate_job_id, get_env_fingerprint

console = Console()


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
        for filename in ["tags.csv", "annotations.json", "rich_truth.json"]:
            path = ctx.output_dir / filename
            if path.exists():
                manifest.add_file(path)

        path = manifest.save()
        console.print(f"[dim]Checksums saved to:[/dim] {path}")
        console.print("[bold green]✓ Generation session complete[/bold green]")

    def _merge_shards(self, output_dir: Path) -> None:
        """Merge shard-specific CSV and JSON files into unified outputs."""
        # Merge CSV
        csv_shards = list(output_dir.glob("tags_shard_*.csv"))
        if csv_shards:
            console.print(f"[dim]Merging {len(csv_shards)} CSV shards...[/dim]")
            with open(output_dir / "tags.csv", "w", newline="") as fout:
                writer = None
                for shard in sorted(csv_shards):
                    with open(shard, newline="") as fin:
                        reader = csv.DictReader(fin)
                        if writer is None:
                            writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
                            writer.writeheader()
                        for row in reader:
                            writer.writerow(row)
                    # shard.unlink()

        # Merge COCO JSON
        coco_shards = list(output_dir.glob("coco_shard_*.json"))
        if coco_shards:
            console.print(f"[dim]Merging {len(coco_shards)} COCO shards...[/dim]")
            merged_coco = {"images": [], "annotations": [], "categories": []}
            categories_map = {}

            for shard in sorted(coco_shards):
                with open(shard) as f:
                    data = json.load(f)

                    # Offset IDs to avoid collisions
                    img_offset = len(merged_coco["images"])
                    ann_offset = len(merged_coco["annotations"])

                    for img in data.get("images", []):
                        img_copy = img.copy()
                        img_copy["id"] += img_offset
                        merged_coco["images"].append(img_copy)

                    for ann in data.get("annotations", []):
                        ann_copy = ann.copy()
                        ann_copy["id"] += ann_offset
                        ann_copy["image_id"] += img_offset
                        merged_coco["annotations"].append(ann_copy)

                    for cat in data.get("categories", []):
                        if cat["name"] not in categories_map:
                            cat_copy = cat.copy()
                            cat_copy["id"] = len(merged_coco["categories"]) + 1
                            merged_coco["categories"].append(cat_copy)
                            categories_map[cat["name"]] = cat_copy["id"]

            with open(output_dir / "annotations.json", "w") as f:
                json.dump(merged_coco, f, indent=2)
            # for shard in coco_shards: shard.unlink()

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
