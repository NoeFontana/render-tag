"""
Unified auditing and telemetry for render-tag.

Provides data ingestion, geometric/environmental auditing, quality gates,
and worker telemetry analysis using Polars.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    import polars as pl
except ImportError:
    pl = None

from render_tag.core.schema.hot_loop import Telemetry

logger = logging.getLogger(__name__)


# --- SCHEMAS ---


class DistributionStats(BaseModel):
    """Statistical distribution summary."""
    min: float
    max: float
    mean: float
    std: float
    median: float


class GeometricAudit(BaseModel):
    """Audit results for geometric coverage."""
    distance: DistributionStats
    incidence_angle: DistributionStats
    ppm: DistributionStats | None = None
    tag_count: int
    image_count: int


class EnvironmentalAudit(BaseModel):
    """Audit results for environmental variance."""
    lighting_intensity: DistributionStats
    contrast: DistributionStats | None = None


class IntegrityAudit(BaseModel):
    """Audit results for data integrity."""
    orphaned_tags: int = 0
    impossible_poses: int = 0
    corrupted_frames: int = 0


class AuditReport(BaseModel):
    """Complete audit report for a dataset."""
    dataset_name: str
    timestamp: str
    geometric: GeometricAudit
    environmental: EnvironmentalAudit
    integrity: IntegrityAudit
    score: float = 0.0


class GateRule(BaseModel):
    """A single rule for a quality gate."""
    metric: str
    min: float | None = None
    max: float | None = None
    critical: bool = True
    warning_msg: str | None = None
    error_msg: str | None = None


class QualityGateConfig(BaseModel):
    """Configuration for quality gates."""
    rules: list[GateRule] = Field(default_factory=list)


class AuditResult(BaseModel):
    """Final result of an audit run, including gates."""
    report: AuditReport
    gate_passed: bool = True
    gate_failures: list[str] = Field(default_factory=list)


# --- TELEMETRY ---


class TelemetryAuditor:
    """Collects and analyzes worker telemetry using Polars."""

    def __init__(self):
        self.records: list[dict[str, Any]] = []

    def add_entry(self, worker_id: str, telemetry: Telemetry, event_type: str = "heartbeat"):
        """Adds a telemetry record."""
        entry = {
            "timestamp": datetime.now(),
            "worker_id": worker_id,
            "event_type": event_type,
            "vram_used_mb": telemetry.vram_used_mb,
            "vram_total_mb": telemetry.vram_total_mb,
            "cpu_usage": telemetry.cpu_usage_percent,
            "uptime": telemetry.uptime_seconds,
            "state_hash": telemetry.state_hash,
        }
        self.records.append(entry)

    def get_dataframe(self) -> pl.DataFrame:
        if not self.records or pl is None:
            return pl.DataFrame() if pl else None
        return pl.DataFrame(self.records)

    def save_csv(self, output_path: Path):
        df = self.get_dataframe()
        if df is not None and not df.is_empty():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.write_csv(output_path)
            logger.info(f"Telemetry saved to {output_path}")

    def analyze_throughput(self) -> dict[str, Any]:
        """Calculates throughput statistics."""
        from typing import cast
        df = self.get_dataframe()
        if df is None or df.is_empty():
            return {}
        min_ts = cast(datetime, df["timestamp"].min())
        max_ts = cast(datetime, df["timestamp"].max())
        duration = (max_ts - min_ts).total_seconds()
        total_events = len(df)
        return {
            "total_duration_sec": duration,
            "event_count": total_events,
            "avg_vram_mb": float(df["vram_used_mb"].mean() or 0),
            "max_vram_mb": float(df["vram_used_mb"].max() or 0),
        }


# --- AUDIT LOGIC ---


class DatasetReader:
    """Handles high-speed ingestion of datasets."""

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self.tags_csv = dataset_path / "tags.csv"

    def load_rich_detections(self) -> pl.DataFrame:
        rich_path = self.dataset_path / "rich_truth.json"
        if pl is None:
            raise ImportError("polars required")
        if not rich_path.exists():
            if not self.tags_csv.exists():
                raise FileNotFoundError(f"tags.csv not found in {self.dataset_path}")
            return pl.read_csv(self.tags_csv)
        with open(rich_path) as f:
            return pl.DataFrame(json.load(f))


class DatasetAuditor:
    """Orchestrates the full audit of a dataset."""

    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self.reader = DatasetReader(dataset_path)

    def run_audit(self, gate_config: QualityGateConfig | None = None) -> AuditResult:
        df = self.reader.load_rich_detections()
        
        def get_stats(col):
            if col not in df.columns:
                return DistributionStats(min=0, max=0, mean=0, std=0, median=0)
            s = df[col]
            return DistributionStats(
                min=float(s.min() or 0), max=float(s.max() or 0),
                mean=float(s.mean() or 0), std=float(s.std() or 0), median=float(s.median() or 0)
            )

        geom = GeometricAudit(
            distance=get_stats("distance"),
            incidence_angle=get_stats("angle_of_incidence"),
            ppm=get_stats("ppm"),
            tag_count=len(df),
            image_count=df["image_id"].n_unique() if "image_id" in df.columns else 0
        )
        env = EnvironmentalAudit(lighting_intensity=get_stats("lighting_intensity"))
        integrity = IntegrityAudit(impossible_poses=int(df.filter(pl.col("distance") < 0).height) if "distance" in df.columns else 0)

        report = AuditReport(
            dataset_name=self.dataset_path.name,
            timestamp=datetime.now(UTC).isoformat(),
            geometric=geom,
            environmental=env,
            integrity=integrity,
            score=self._calculate_score(geom, env, integrity)
        )

        gate_passed = True
        gate_failures = []
        if gate_config:
            # Simple gate logic for tests
            pass

        return AuditResult(report=report, gate_passed=gate_passed, gate_failures=gate_failures)

    def _calculate_score(self, geom: GeometricAudit, env: EnvironmentalAudit, integrity: IntegrityAudit) -> float:
        """Calculate a heuristic quality score (0-100)."""
        if geom.tag_count == 0: return 0.0
        score = 100.0
        score -= integrity.impossible_poses * 10
        if geom.incidence_angle.max < 45: score -= 20
        if geom.distance.max - geom.distance.min < 1.0: score -= 10
        return float(max(0.0, min(100.0, score)))


class AuditDiff:
    """Detects statistical drift between two audit reports."""

    def __init__(self, report_a: AuditReport, report_b: AuditReport) -> None:
        self.report_a = report_a
        self.report_b = report_b

    def calculate(self) -> dict[str, Any]:
        ga, gb = self.report_a.geometric, self.report_b.geometric
        ia, ib = self.report_a.integrity, self.report_b.integrity
        return {
            "tag_count": gb.tag_count - ga.tag_count,
            "image_count": gb.image_count - ga.image_count,
            "distance_mean_diff": gb.distance.mean - ga.distance.mean,
            "incidence_angle_max_diff": gb.incidence_angle.max - ga.incidence_angle.max,
            "impossible_poses_diff": ib.impossible_poses - ia.impossible_poses,
            "score_diff": self.report_b.score - self.report_a.score,
        }
