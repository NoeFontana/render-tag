import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Annotated, Any

import typer
from datasets import Dataset, Features, Image, Sequence, Value, load_dataset

app = typer.Typer(help="Bidirectional Dataset Infrastructure for render-tag-bench")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub_manager")


def get_dataset_features() -> Features:
    """Define the Cog-First Dataset Features (Schema)."""
    return Features(
        {
            "image": Image(),
            "image_id": Value("string"),
            "scene_id": Value("int32"),
            "camera_idx": Value("int32"),
            "tag_id": Value("int32"),
            "tag_family": Value("string"),
            "corners": Sequence(Sequence(Value("float32"), length=2), length=4),
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
        logger.error(f"Images directory not found: {images_dir}")
        return

    # Find all meta.json files
    meta_files = sorted(images_dir.glob("*_meta.json"))
    logger.info(f"Found {len(meta_files)} metadata files in {images_dir}")

    for meta_path in meta_files:
        try:
            with open(meta_path) as f:
                meta = json.load(f)

            image_name = meta_path.name.replace("_meta.json", "")
            image_path = images_dir / f"{image_name}.png"

            if not image_path.exists():
                logger.warning(f"Image not found for meta {meta_path.name}")
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
            logger.error(f"Error processing {meta_path}: {e}")


@app.command()
def upload(
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
    """Staff-Level Utility to push a render subset to Hugging Face Hub."""
    logger.info(f"🚀 Preparing upload for config: {config_name}")

    ds = Dataset.from_generator(
        render_generator, gen_kwargs={"data_dir": data_dir}, features=get_dataset_features()
    )

    logger.info(f"📊 Created dataset with {len(ds)} records")

    if dry_run:
        logger.info("✨ Dry run complete. No data was uploaded.")
        if len(ds) > 0:
            logger.info(f"Sample record: {ds[0]}")
        return

    logger.info(f"☁️ Pushing to {repo_id} ({config_name}) on branch {revision}...")
    ds.push_to_hub(
        repo_id=repo_id,
        config_name=config_name,
        split=split,
        revision=revision,
        private=private,
        embed_external_files=True,
    )
    logger.info("✅ Upload successful!")


@app.command()
def download(
    repo_id: Annotated[str, typer.Argument(help="Hugging Face repo ID")],
    output_dir: Annotated[Path, typer.Argument(help="Local directory to restore files to")],
    config_name: Annotated[str, typer.Option(help="The subset/configuration name")] = "default",
    split: Annotated[str, typer.Option(help="The dataset split")] = "train",
    revision: Annotated[str, typer.Option(help="The branch/revision to load from")] = "main",
    limit: Annotated[int | None, typer.Option(help="Limit number of images to download")] = None,
):
    """Staff-Level Utility to download a subset and restore the local render-tag structure."""
    logger.info(f"📥 Downloading {repo_id} ({config_name}) to {output_dir}")

    # 1. Load dataset
    ds = load_dataset(repo_id, name=config_name, split=split, revision=revision, streaming=True)

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # We use a dictionary to accumulate detections per image_id
    # since the Hub format exploded them for Parquet.
    image_metadata = {}
    image_objects = {}

    logger.info("Streaming dataset and accumulating records...")

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

    logger.info(f"Restoring {len(image_metadata)} images and sidecars to {images_dir}...")

    for image_id, detections in image_metadata.items():
        # 2. Save Image
        image_path = images_dir / f"{image_id}.png"
        image_objects[image_id].save(image_path)

        # 3. Save sidecar _meta.json
        meta_path = images_dir / f"{image_id}_meta.json"

        # We wrap in a default 'provenance' and 'detections' structure
        # to match the render-tag output format.
        meta_content = {
            "detections": detections,
            "provenance": {
                "restored_from_hub": True,
                "repo_id": repo_id,
                "config_name": config_name,
                "revision": revision,
            },
        }

        with open(meta_path, "w") as f:
            json.dump(meta_content, f, indent=2)

    logger.info(f"✅ Successfully restored {len(image_metadata)} scenes (images + metadata).")


if __name__ == "__main__":
    app()
