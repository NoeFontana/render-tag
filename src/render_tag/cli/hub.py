"""
Hugging Face Hub management commands.
"""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Annotated, Any
from collections import defaultdict

import typer

try:
    from datasets import Dataset, Features, Image, Sequence, Value, load_dataset
except ImportError:
    Dataset = None
    Features = None
    Image = None
    Sequence = None
    Value = None
    load_dataset = None

from render_tag.core.logging import get_logger
from render_tag.orchestration.assets import AssetManager

from .tools import check_hub_installed, console

logger = get_logger(__name__)
app = typer.Typer(help="Manage datasets and assets on Hugging Face Hub.")


def _ensure_hub():
    if not check_hub_installed():
        console.print("[bold red]Error:[/bold red] Hub management dependencies not installed.")
        console.print("Install with: [cyan]pip install 'render-tag[hub]'[/cyan]")
        raise typer.Exit(code=1)


def get_dataset_features() -> Any:
    """Define the Cog-First Dataset Features (Schema).
    
    This schema is image-centric. Each row represents one image, 
    and tag-related metadata fields are Sequences (lists).
    """
    return Features(
        {
            "image": Image(),
            "image_id": Value("string"),
            "scene_id": Value("int32"),
            "camera_idx": Value("int32"),
            "tag_id": Sequence(Value("int32")),
            "tag_family": Sequence(Value("string")),
            "corners": Sequence(Sequence(Sequence(Value("float32"), length=2))),
            "distance": Sequence(Value("float32")),
            "angle_of_incidence": Sequence(Value("float32")),
            "pixel_area": Sequence(Value("float32")),
            "occlusion_ratio": Sequence(Value("float32")),
            "ppm": Sequence(Value("float32")),
            "position": Sequence(Sequence(Value("float32"), length=3)),
            "rotation_quaternion": Sequence(Sequence(Value("float32"), length=4)),
            "metadata": Sequence(Value("string")),  # orjson serialized extra metadata
        }
    )


def render_generator(data_dir: Path) -> Generator[dict[str, Any], None, None]:
    """Scans directory and yields image-centric dataset records."""
    images_dir = data_dir / "images"
    if not images_dir.exists():
        console.print(f"[red]Error:[/red] Images directory not found: {images_dir}")
        return

    # Grouped records: image_id -> list of tag records
    grouped_data = defaultdict(list)

    # 1. New Format: Read from rich_truth.json if it exists
    rich_truth_path = data_dir / "rich_truth.json"
    if rich_truth_path.exists():
        console.print(f"[dim]Found rich_truth.json in {data_dir}[/dim]")
        try:
            with open(rich_truth_path) as f:
                records = json.load(f)
            for record in records:
                image_id = record.get("image_id")
                if image_id:
                    grouped_data[image_id].append(record)
        except Exception as e:
            logger.error("Error processing rich_truth.json", error=str(e))
            console.print(f"[red]Error processing rich_truth.json:[/red] {e}")

    # 2. Legacy Format: Fallback to reading individual _meta.json files
    else:
        meta_files = sorted(images_dir.glob("*_meta.json"))
        console.print(f"[dim]Found {len(meta_files)} metadata files in {images_dir}[/dim]")
        for meta_path in meta_files:
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                image_name = meta_path.name.replace("_meta.json", "")
                detections = meta.get("detections", [])
                for det in detections:
                    grouped_data[image_name].append(det)
            except Exception as e:
                console.print(f"[red]Error processing {meta_path.name}:[/red] {e}")

    # 3. Yield image-centric records
    for image_id, tags in grouped_data.items():
        image_path = images_dir / f"{image_id}.png"
        if not image_path.exists():
            continue

        parts = image_id.split("_")
        scene_id = int(parts[1]) if len(parts) > 1 else 0
        camera_idx = int(parts[3]) if len(parts) > 3 else 0

        # Aggregate per-tag fields into sequences
        yield {
            "image": str(image_path),
            "image_id": image_id,
            "scene_id": scene_id,
            "camera_idx": camera_idx,
            "tag_id": [t.get("tag_id", 0) for t in tags],
            "tag_family": [t.get("tag_family", "unknown") for t in tags],
            "corners": [t.get("corners", []) for t in tags],
            "distance": [t.get("distance", 0.0) for t in tags],
            "angle_of_incidence": [t.get("angle_of_incidence", 0.0) for t in tags],
            "pixel_area": [t.get("pixel_area", 0.0) for t in tags],
            "occlusion_ratio": [t.get("occlusion_ratio", 0.0) for t in tags],
            "ppm": [t.get("ppm", 0.0) for t in tags],
            "position": [t.get("position", [0.0, 0.0, 0.0]) for t in tags],
            "rotation_quaternion": [t.get("rotation_quaternion", [1.0, 0.0, 0.0, 0.0]) for t in tags],
            "metadata": [json.dumps(t.get("metadata", {})) for t in tags],
        }


@app.command(name="push-dataset")
def push_dataset(
    data_dir: Annotated[Path, typer.Argument(help="Local directory containing rendered results")],
    repo_id: Annotated[
        str, typer.Argument(help="Hugging Face repo ID (e.g. 'org/render-tag-bench')")
    ],
    config_name: Annotated[str, typer.Option(help="The subset/configuration name")] = "default",
    split: Annotated[str, typer.Option(help="The dataset split")] = "train",
    revision: Annotated[str, typer.Option(help="The branch/revision to push to")] = "main",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Verify locally without uploading")
    ] = False,
    private: Annotated[
        bool, typer.Option(help="Whether the repo should be private if created")
    ] = False,
):
    """Push a render subset to Hugging Face Hub (Parquet)."""
    _ensure_hub()
    console.print(f"[bold blue]🚀 Preparing upload for config:[/bold blue] {config_name}")

    ds = Dataset.from_generator(
        render_generator, gen_kwargs={"data_dir": data_dir}, features=get_dataset_features()
    )

    console.print(f"[bold green]📊 Created dataset with {len(ds)} images (deduplicated)[/bold green]")

    if dry_run:
        console.print("[yellow]✨ Dry run complete. No data was uploaded.[/yellow]")
        return

    console.print(f"[dim]☁️ Pushing to {repo_id} ({config_name}) on branch {revision}...[/dim]")
    ds.push_to_hub(
        repo_id=repo_id,
        config_name=config_name,
        split=split,
        revision=revision,
        private=private,
        embed_external_files=True,
    )

    # Upload consolidated metadata files
    from huggingface_hub import HfApi

    api = HfApi()

    metadata_files = [
        "checksums.json",
        "coco_labels.json",
        "ground_truth.csv",
        "job_spec.json",
        "manifest.json",
        "provenance.json",
        "rich_truth.json",
    ]
    for file_name in metadata_files:
        file_path = data_dir / file_name
        if file_path.exists():
            console.print(f"[dim]☁️ Pushing {file_name} to {repo_id}...[/dim]")
            api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=f"{config_name}/{file_name}",
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
            )

    console.print("[bold green]✅ Upload successful![/bold green]")


@app.command(name="pull-dataset")
def pull_dataset(
    repo_id: Annotated[str, typer.Argument(help="Hugging Face repo ID")],
    output_dir: Annotated[Path, typer.Argument(help="Local directory to restore files to")],
    config_name: Annotated[str, typer.Option(help="The subset/configuration name")] = "default",
    split: Annotated[str, typer.Option(help="The dataset split")] = "train",
    revision: Annotated[str, typer.Option(help="The branch/revision to load from")] = "main",
    limit: Annotated[int | None, typer.Option(help="Limit number of images to download")] = None,
):
    """Download a subset and restore the local render-tag structure."""
    _ensure_hub()
    console.print(
        f"[bold blue]📥 Downloading {repo_id} ({config_name}) to:[/bold blue] {output_dir}"
    )

    # 1. Load dataset
    ds = load_dataset(repo_id, name=config_name, split=split, revision=revision, streaming=True)

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    rich_truth_data = []
    count = 0

    console.print("[dim]Streaming dataset and restoring images...[/dim]")

    for record in ds:
        image_id = record["image_id"]
        img = record["image"]
        
        # Save image
        image_path = images_dir / f"{image_id}.png"
        img.save(image_path)

        # Reconstruct per-tag records from sequences
        # All sequences have the same length N (number of tags in this image)
        num_tags = len(record["tag_id"])
        for i in range(num_tags):
            det = {
                "image_id": image_id,
                "tag_id": record["tag_id"][i],
                "tag_family": record["tag_family"][i],
                "corners": record["corners"][i],
                "distance": record["distance"][i],
                "angle_of_incidence": record["angle_of_incidence"][i],
                "pixel_area": record["pixel_area"][i],
                "occlusion_ratio": record["occlusion_ratio"][i],
                "ppm": record["ppm"][i],
                "position": record["position"][i],
                "rotation_quaternion": record["rotation_quaternion"][i],
                "metadata": json.loads(record["metadata"][i]),
            }
            rich_truth_data.append(det)

        count += 1
        if limit and count >= limit:
            break

    # Restore rich_truth.json
    rich_truth_path = output_dir / "rich_truth.json"
    with open(rich_truth_path, "w") as f:
        json.dump(rich_truth_data, f, indent=2)

    # Attempt to download other metadata files directly
    from huggingface_hub import hf_hub_download

    metadata_files = [
        "checksums.json",
        "coco_labels.json",
        "ground_truth.csv",
        "job_spec.json",
        "manifest.json",
        "provenance.json",
    ]
    for file_name in metadata_files:
        try:
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=f"{config_name}/{file_name}",
                repo_type="dataset",
                revision=revision,
            )
            import shutil

            shutil.copy2(downloaded_path, output_dir / file_name)
        except Exception:
            # File might not exist in the repo, that's okay
            pass

    console.print(f"[bold green]✅ Successfully restored {count} scenes.[/bold green]")


@app.command(name="pull-assets")
def pull_assets(
    repo_id: Annotated[
        str, typer.Option(help="Hugging Face Asset Repo")
    ] = "NoeFontana/render-tag-assets",
    local_dir: Annotated[Path, typer.Option(help="Local assets directory")] = Path("assets"),
    token: Annotated[str | None, typer.Option(envvar="HF_TOKEN")] = None,
):
    """Synchronize binary assets (textures, HDRIs) from the Hub to local."""
    console.print(f"[bold blue]📥 Pulling assets from {repo_id} to:[/bold blue] {local_dir}")
    manager = AssetManager(local_dir=local_dir, repo_id=repo_id)
    manager.pull(token=token)
    console.print("[bold green]✅ Assets synchronized![/bold green]")


@app.command(name="push-assets")
def push_assets(
    repo_id: Annotated[
        str, typer.Option(help="Hugging Face Asset Repo")
    ] = "NoeFontana/render-tag-assets",
    local_dir: Annotated[Path, typer.Option(help="Local assets directory")] = Path("assets"),
    commit_message: Annotated[str, typer.Option("-m", help="Commit message")] = "Update assets",
    token: Annotated[str | None, typer.Option(envvar="HF_TOKEN")] = None,
):
    """Upload local binary assets to the Hub."""
    console.print(f"[bold blue]📤 Pushing assets from {local_dir} to:[/bold blue] {repo_id}")
    manager = AssetManager(local_dir=local_dir, repo_id=repo_id)
    manager.push(token=token, commit_message=commit_message)
    console.print("[bold green]✅ Assets pushed![/bold green]")
