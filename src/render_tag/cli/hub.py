"""
Hugging Face Hub management commands.
"""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Annotated, Any

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
    """Define the Cog-First Dataset Features (Schema)."""
    return Features(
        {
            "image": Image(),
            "image_id": Value("string"),
            "scene_id": Value("int32"),
            "camera_idx": Value("int32"),
            "tag_id": Value("int32"),
            "tag_family": Value("string"),
            "corners": Sequence(Sequence(Value("float32"), length=2)),
            "distance": Value("float32"),
            "angle_of_incidence": Value("float32"),
            "pixel_area": Value("float32"),
            "occlusion_ratio": Value("float32"),
            "ppm": Value("float32"),
            "position": Sequence(Value("float32"), length=3),
            "rotation_quaternion": Sequence(Value("float32"), length=4),
            "metadata": Value("string"),  # orjson serialized extra metadata
        }
    )


def render_generator(data_dir: Path) -> Generator[dict[str, Any], None, None]:
    """Scans directory and yields dataset records."""
    images_dir = data_dir / "images"
    if not images_dir.exists():
        console.print(f"[red]Error:[/red] Images directory not found: {images_dir}")
        return

    # 1. New Format: Read from rich_truth.json if it exists
    rich_truth_path = data_dir / "rich_truth.json"
    if rich_truth_path.exists():
        console.print(f"[dim]Found rich_truth.json in {data_dir}[/dim]")
        try:
            with open(rich_truth_path) as f:
                records = json.load(f)

            for record in records:
                image_id = record.get("image_id")
                if not image_id:
                    continue

                image_path = images_dir / f"{image_id}.png"
                if not image_path.exists():
                    logger.warning(
                        "Image not found for record", image_id=image_id, path=str(image_path)
                    )
                    continue

                parts = image_id.split("_")
                scene_id = int(parts[1]) if len(parts) > 1 else 0
                camera_idx = int(parts[3]) if len(parts) > 3 else 0

                yield {
                    "image": str(image_path),
                    "image_id": image_id,
                    "scene_id": scene_id,
                    "camera_idx": camera_idx,
                    "tag_id": record.get("tag_id", 0),
                    "tag_family": record.get("tag_family", "unknown"),
                    "corners": record.get("corners", []),
                    "distance": record.get("distance", 0.0),
                    "angle_of_incidence": record.get("angle_of_incidence", 0.0),
                    "pixel_area": record.get("pixel_area", 0.0),
                    "occlusion_ratio": record.get("occlusion_ratio", 0.0),
                    "ppm": record.get("ppm", 0.0),
                    "position": record.get("position", [0.0, 0.0, 0.0]),
                    "rotation_quaternion": record.get("rotation_quaternion", [1.0, 0.0, 0.0, 0.0]),
                    "metadata": json.dumps(record.get("metadata", {})),
                }
        except Exception as e:
            logger.error("Error processing rich_truth.json", error=str(e), exc_info=True)
            console.print(f"[red]Error processing rich_truth.json:[/red] {e}")
        return

    # 2. Legacy Format: Fallback to reading individual _meta.json files
    meta_files = sorted(images_dir.glob("*_meta.json"))
    console.print(f"[dim]Found {len(meta_files)} metadata files in {images_dir}[/dim]")

    for meta_path in meta_files:
        try:
            with open(meta_path) as f:
                meta = json.load(f)

            image_name = meta_path.name.replace("_meta.json", "")
            image_path = images_dir / f"{image_name}.png"

            if not image_path.exists():
                console.print(
                    f"[yellow]Warning:[/yellow] Image not found for meta {meta_path.name}"
                )
                continue

            parts = image_name.split("_")
            scene_id = int(parts[1])
            camera_idx = int(parts[3])

            detections = meta.get("detections", [])
            if not detections:
                continue

            for det in detections:
                record = {
                    "image": str(image_path),
                    "image_id": image_name,
                    "scene_id": scene_id,
                    "camera_idx": camera_idx,
                    "tag_id": det.get("tag_id", 0),
                    "tag_family": det.get("tag_family", "unknown"),
                    "corners": det.get("corners", []),
                    "distance": det.get("distance", 0.0),
                    "angle_of_incidence": det.get("angle_of_incidence", 0.0),
                    "pixel_area": det.get("pixel_area", 0.0),
                    "occlusion_ratio": det.get("occlusion_ratio", 0.0),
                    "ppm": det.get("ppm", 0.0),
                    "position": det.get("position", [0.0, 0.0, 0.0]),
                    "rotation_quaternion": det.get("rotation_quaternion", [1.0, 0.0, 0.0, 0.0]),
                    "metadata": json.dumps(det.get("metadata", {})),
                }
                yield record

        except Exception as e:
            console.print(f"[red]Error processing {meta_path.name}:[/red] {e}")


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

    console.print(f"[bold green]📊 Created dataset with {len(ds)} records[/bold green]")

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

    image_metadata = {}
    image_objects = {}

    console.print("[dim]Streaming dataset and accumulating records...[/dim]")

    for record in ds:
        image_id = record["image_id"]

        if image_id not in image_metadata:
            image_metadata[image_id] = []
            image_objects[image_id] = record["image"]

        # Reconstruct the detection record
        det = {
            "tag_id": record["tag_id"],
            "tag_family": record["tag_family"],
            "corners": record["corners"],
            "distance": record["distance"],
            "angle_of_incidence": record["angle_of_incidence"],
            "pixel_area": record["pixel_area"],
            "occlusion_ratio": record["occlusion_ratio"],
            "ppm": record["ppm"],
            "position": record["position"],
            "rotation_quaternion": record["rotation_quaternion"],
            "metadata": json.loads(record["metadata"]),
        }
        image_metadata[image_id].append(det)

        if limit and len(image_metadata) >= limit:
            break

    console.print(f"[dim]Restoring {len(image_objects)} images...[/dim]")

    for image_id, img in image_objects.items():
        image_path = images_dir / f"{image_id}.png"
        img.save(image_path)

    # Reconstruct rich_truth.json instead of per-image metadata
    rich_truth_path = output_dir / "rich_truth.json"
    rich_truth_data = []
    for image_id, detections in image_metadata.items():
        for det in detections:
            # Format according to new benchmark structure
            rich_truth_data.append(
                {
                    "image_id": image_id,
                    **det,
                }
            )

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

    console.print(f"[bold green]✅ Successfully restored {len(image_objects)} scenes.[/bold green]")


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
