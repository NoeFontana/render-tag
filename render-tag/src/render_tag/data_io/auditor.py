"""
Auditor Data Ingestion for render-tag.

Uses Polars for high-performance vectorized loading of datasets.
"""

import json
from pathlib import Path
from typing import Any

import polars as pl


class DatasetReader:
    """Handles high-speed ingestion of render-tag datasets."""

    def __init__(self, dataset_path: Path) -> None:
        """Initialize the reader with a dataset directory.

        Args:
            dataset_path: Path to the dataset root.
        """
        self.dataset_path = dataset_path
        self.tags_csv = dataset_path / "tags.csv"
        self.manifest_json = dataset_path / "manifest.json"
        self.images_dir = dataset_path / "images"

    def load_detections(self) -> pl.DataFrame:
        """Load tags.csv into a Polars DataFrame.

        Returns:
            DataFrame containing tag detections.
        """
        if not self.tags_csv.exists():
            raise FileNotFoundError(f"tags.csv not found in {self.dataset_path}")

        return pl.read_csv(self.tags_csv)

    def load_full_dataset(self) -> pl.DataFrame:
        """Load detections and join with sidecar metadata.

        Returns:
            DataFrame containing detections and per-image metadata.
        """
        df = self.load_detections()
        
        # Identify unique image IDs
        image_ids = df["image_id"].unique().to_list()
        
        metadata_records = []
        for img_id in image_ids:
            meta_path = self.images_dir / f"{img_id}_meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta_data = json.load(f)
                
                # Flatten the metadata we care about
                # For now, we extract lighting intensity as a proof of concept
                # In the future, this can be more generic
                record = {
                    "image_id": img_id,
                    "lighting_intensity": meta_data.get("recipe_snapshot", {})
                    .get("world", {})
                    .get("lighting", {})
                    .get("intensity", 0.0),
                }
                metadata_records.append(record)
        
        if not metadata_records:
            return df
            
        meta_df = pl.DataFrame(metadata_records)
        return df.join(meta_df, on="image_id", how="left")
