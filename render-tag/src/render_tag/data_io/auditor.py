"""
Auditor Data Ingestion for render-tag.

Uses Polars for high-performance vectorized loading of datasets.
"""

import json
from pathlib import Path
from typing import Any

import polars as pl

from .auditor_schema import (
    AuditReport,
    DistributionStats,
    EnvironmentalAudit,
    GeometricAudit,
    IntegrityAudit,
)


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

    def load_rich_detections(self) -> pl.DataFrame:
        """Load rich_truth.json into a Polars DataFrame.

        Returns:
            DataFrame containing rich tag detections.
        """
        rich_path = self.dataset_path / "rich_truth.json"
        if not rich_path.exists():
            # Fallback to metadata join if rich_truth is missing
            return self.load_full_dataset()

        with open(rich_path) as f:
            data = json.load(f)

        return pl.DataFrame(data)


class GeometryAuditor:
    """Audits geometric coverage of a dataset."""

    def __init__(self, df: pl.DataFrame) -> None:
        """Initialize with a detections DataFrame.

        Args:
            df: DataFrame containing 'distance' and 'angle_of_incidence'.
        """
        self.df = df

    def audit(self) -> GeometricAudit:
        """Perform geometric audit.

        Returns:
            GeometricAudit report.
        """
        # Ensure columns exist, fill with 0 if missing (though they should be there)
        cols = self.df.columns
        dist_col = "distance" if "distance" in cols else None
        angle_col = "angle_of_incidence" if "angle_of_incidence" in cols else None

        return GeometricAudit(
            distance=self._calculate_dist_stats(dist_col),
            incidence_angle=self._calculate_dist_stats(angle_col),
            tag_count=len(self.df),
            image_count=self.df["image_id"].n_unique(),
        )

    def _calculate_dist_stats(self, col: str | None) -> DistributionStats:
        """Calculate distribution statistics for a column."""
        if col is None or len(self.df) == 0:
            return DistributionStats(min=0, max=0, mean=0, std=0, median=0)

        # Polars makes this extremely fast
        series = self.df[col]
        return DistributionStats(
            min=float(series.min() or 0.0),
            max=float(series.max() or 0.0),
            mean=float(series.mean() or 0.0),
            std=float(series.std() or 0.0),
            median=float(series.median() or 0.0),
        )


class EnvironmentalAuditor:
    """Audits environmental variance (lighting, etc.)."""

    def __init__(self, df: pl.DataFrame) -> None:
        self.df = df

    def audit(self) -> EnvironmentalAudit:
        """Perform environmental audit."""
        cols = self.df.columns
        light_col = "lighting_intensity" if "lighting_intensity" in cols else None

        return EnvironmentalAudit(
            lighting_intensity=self._calculate_dist_stats(light_col),
        )

    def _calculate_dist_stats(self, col: str | None) -> DistributionStats:
        """Calculate distribution statistics for a column."""
        if col is None or len(self.df) == 0:
            return DistributionStats(min=0, max=0, mean=0, std=0, median=0)

        series = self.df[col]
        return DistributionStats(
            min=float(series.min() or 0.0),
            max=float(series.max() or 0.0),
            mean=float(series.mean() or 0.0),
            std=float(series.std() or 0.0),
            median=float(series.median() or 0.0),
        )


class IntegrityAuditor:
    """Audits dataset integrity and identifies corrupted data."""

    def __init__(self, df: pl.DataFrame) -> None:
        self.df = df

    def audit(self) -> IntegrityAudit:
        """Perform integrity audit."""
        impossible = 0
        if "distance" in self.df.columns:
            impossible = int(self.df.filter(pl.col("distance") < 0).height)

        return IntegrityAudit(
            impossible_poses=impossible,
            orphaned_tags=0,  # TODO: Implement directory-based check
            corrupted_frames=0,
        )


class DatasetAuditor:
    """Orchestrates the full audit of a dataset."""

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self.reader = DatasetReader(dataset_path)

    def run_audit(self) -> AuditReport:
        """Run all auditors and compile the final report.

        Returns:
            AuditReport object.
        """
        import datetime

        # 1. Load Data (Prefer Rich)
        df = self.reader.load_rich_detections()

        # 2. Run Individual Auditors
        geom_results = GeometryAuditor(df).audit()
        env_results = EnvironmentalAuditor(df).audit()
        integrity_results = IntegrityAuditor(df).audit()

        # 3. Compile Report
        return AuditReport(
            dataset_name=self.dataset_path.name,
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            geometric=geom_results,
            environmental=env_results,
            integrity=integrity_results,
            score=self._calculate_score(geom_results, env_results, integrity_results),
        )

    def _calculate_score(
        self, geom: GeometricAudit, env: EnvironmentalAudit, integrity: IntegrityAudit
    ) -> float:
        """Calculate a heuristic quality score (0-100)."""
        if geom.tag_count == 0:
            return 0.0

        score = 100.0
        # Penalize for integrity issues
        score -= integrity.impossible_poses * 10
        score -= integrity.orphaned_tags * 5
        score -= integrity.corrupted_frames * 20

        # Penalize for lack of geometric variance (very basic heuristic)
        if geom.incidence_angle.max < 45:
            score -= 20
        if geom.distance.max - geom.distance.min < 1.0:
            score -= 10

        return float(max(0.0, min(100.0, score)))
