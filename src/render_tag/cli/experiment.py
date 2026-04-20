"""
Experiment commands.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer

from render_tag.audit.reporting import generate_dataset_info
from render_tag.core.manifest import ChecksumManifest
from render_tag.core.validator import validate_recipe_file
from render_tag.generation.compiler import SceneCompiler
from render_tag.generation.tags import ensure_tag_asset
from render_tag.orchestration import ResponseStatus, UnifiedWorkerOrchestrator
from render_tag.orchestration.experiment import (
    expand_campaign,
    expand_experiment,
    load_experiment_config,
)
from render_tag.orchestration.experiment_schema import Campaign

from .tools import (
    check_blenderproc_installed,
    console,
    serialize_config_to_json,
)

app = typer.Typer(help="Run experiments.")


@app.command(name="run")
def run(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to the experiment configuration YAML file",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        "output/experiments",
        "--output",
        "-o",
        help="Base output directory for experiment results",
        resolve_path=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    renderer_mode: str = typer.Option(
        "cycles",
        "--renderer-mode",
        "-r",
        help="Rendering engine: cycles, workbench, eevee",
    ),
    skip_render: bool = typer.Option(
        False,
        "--skip-render",
        help="Skip the long rendering cycle (Shadow Render only)",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        help="Parallel workers per variant (1-10; capped by the 10-port budget per variant)",
    ),
) -> None:
    """
    Run a controlled experiment (Parameter Sweep).

    Generates multiple datasets based on sweep definitions, keeping other
    variables constant (ceteris paribus).
    """
    # Check dependencies
    if not check_blenderproc_installed():
        console.print("[bold red]Error:[/bold red] blenderproc not installed.")
        raise typer.Exit(code=1) from None

    if not 1 <= workers <= 10:
        console.print(
            "[bold red]Error:[/bold red] --workers must be between 1 and 10 "
            "(per-variant port budget is 10)."
        )
        raise typer.Exit(code=1) from None

    # Load Experiment
    console.print(f"[dim]Loading experiment from[/dim] {config}")
    try:
        exp_or_campaign = load_experiment_config(config)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Invalid experiment config: {e}")
        raise typer.Exit(code=1) from None

    # Expand Variants
    if isinstance(exp_or_campaign, Campaign):
        # Campaign logic
        # Respect CLI output as base, join with Campaign output_dir
        exp_dir = output / exp_or_campaign.output_dir
        exp_or_campaign.output_dir = str(exp_dir)

        variants = expand_campaign(exp_or_campaign)
        console.print(f"[bold]Found {len(variants)} sub-experiments[/bold] in campaign")
        exp_name = "campaign"

    else:
        # Standard Experiment
        variants = expand_experiment(exp_or_campaign)
        console.print(
            f"[bold]Found {len(variants)} variants[/bold] for experiment '{exp_or_campaign.name}'"
        )
        exp_name = exp_or_campaign.name
        exp_dir = output / exp_name

    exp_dir.mkdir(parents=True, exist_ok=True)

    # Execute Variants
    for i, variant in enumerate(variants):
        console.print(f"\n[bold cyan]Run {i + 1}/{len(variants)}: {variant.variant_id}[/bold cyan]")
        console.print(f"[dim]Description: {variant.description}[/dim]")

        # Determine variant output directory
        if isinstance(exp_or_campaign, Campaign):
            variant_dir = variant.config.dataset.output_dir
        else:
            variant_dir = output / exp_name / variant.variant_id
            variant.config.dataset.output_dir = variant_dir

        variant_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate Recipes
        compiler = SceneCompiler(variant.config, output_dir=variant_dir)
        recipes = compiler.compile_shards(shard_index=0, total_shards=1, validate=True)
        recipe_path = variant_dir / "scene_recipes.json"
        compiler.save_recipe_json(recipes, "scene_recipes.json")

        # 2. Save Checksum Manifest (Pre-execution)
        manifest = ChecksumManifest(
            job_id=f"{exp_name}_{variant.variant_id}", output_dir=variant_dir
        )
        # We'll add files AFTER generation, but we can initialize it here.

        # 3. Serialize Config for BlenderProc
        job_config_path = variant_dir / "generation_config.json"
        serialize_config_to_json(variant.config, job_config_path)

        # 4. Ensure Assets (Pre-generate tags into cache matching recipes)
        cache_tag_dir = variant_dir / "cache" / "tags"
        cache_tag_dir.mkdir(parents=True, exist_ok=True)

        required_tags = set()
        for recipe in recipes:
            for obj in recipe.objects:
                if obj.type == "TAG":
                    family = obj.properties.get("tag_family")
                    tag_id = obj.properties.get("tag_id")
                    margin_bits = obj.properties.get("margin_bits", 0)
                    if family and tag_id is not None:
                        required_tags.add((family, tag_id, margin_bits))

        if required_tags:
            console.print(f"[dim]Pre-generating {len(required_tags)} unique tags...[/dim]")
            for family, tag_id, margin_bits in required_tags:
                ensure_tag_asset(family, tag_id, cache_tag_dir, margin_bits=margin_bits)

        # 4.5 Validate Recipes (Shadow Render logic)
        is_valid, errors, warnings = validate_recipe_file(recipe_path)
        if warnings:
            for w in warnings:
                console.print(f"[yellow]Warning:[/yellow] {w}")
        if not is_valid:
            console.print(
                f"[bold red]Recipe Validation Failed for variant {variant.variant_id}![/bold red]"
            )
            for e in errors:
                console.print(f"[red]  - {e}[/red]")
            raise typer.Exit(code=1) from None

        # 5. Run BlenderProc (via Orchestrator)
        if skip_render:
            console.print("[green]Shadow Render Validation Complete (Skip Render enabled).[/green]")
            continue

        try:
            # Use Orchestrator to execute recipes
            # We use a unique base port to avoid collisions if running multiple experiments
            with UnifiedWorkerOrchestrator(
                num_workers=workers,
                base_port=21000 + (i * 10),
                ephemeral=True,
                max_renders_per_worker=len(recipes),
                mock=(renderer_mode == "mock"),
                seed=variant.config.dataset.seed,
            ) as orchestrator:
                orchestrator.start(shard_id=f"exp_{variant.variant_id}")

                sid = f"exp_{variant.variant_id}"

                def _render(recipe, out=variant_dir, rm=renderer_mode, s=sid):
                    return orchestrator.execute_recipe(
                        recipe.model_dump(mode="json"), out, rm, sid=s
                    )

                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(_render, r) for r in recipes]
                    for fut in as_completed(futures):
                        resp = fut.result()
                        if resp.status != ResponseStatus.SUCCESS:
                            console.print(
                                f"[bold red]Variant {variant.variant_id} Failed![/bold red]"
                            )
                            console.print(f"[red]Render error: {resp.message}[/red]")
                            raise typer.Exit(code=1) from None

            # 6. Generate Unified Manifest
            generate_dataset_info(
                dataset_dir=variant_dir,
                config=variant.config,
                experiment_info={
                    "name": variant.experiment_name,
                    "variant_id": variant.variant_id,
                    "description": variant.description,
                    "overrides": variant.overrides,
                },
                cli_args=sys.argv,
            )

            # 7. Generate Checksums
            manifest.add_directory(variant_dir / "images", pattern="*.png")
            if (variant_dir / "tags.csv").exists():
                manifest.add_file(variant_dir / "tags.csv")
            manifest.save()

            console.print(f"[green]✓ {variant.variant_id} Complete[/green]")

        except Exception as e:
            console.print(f"[bold red]Error running experiment variant:[/bold red] {e}")
            raise typer.Exit(code=1) from None

    console.print("\n[bold green]Experiment Completed Successfully![/bold green]")
    console.print(f"[dim]Results:[/dim] {exp_dir}")
