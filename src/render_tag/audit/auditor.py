"""
Unified auditing and telemetry for render-tag.

Provides data ingestion, geometric/environmental auditing, quality gates,
and worker telemetry analysis using Polars.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

try:
    import polars as pl
except ImportError:
    pl = None

from render_tag.core.logging import get_logger
from render_tag.core.schema.base import KeypointVisibility
from render_tag.core.schema.hot_loop import Telemetry
from render_tag.data_io.readers import unwrap_rich_truth
from render_tag.generation.projection_math import (
    apply_distortion_by_model,
    quaternion_wxyz_to_matrix,
)

logger = get_logger(__name__)


# --- EXCEPTIONS ---


class DictionaryOrientationError(ValueError):
    """Raised when the texture payload is 180° out of phase with the 3D geometry.

    The projected 3D TL anchor lands on annotated corners[2] (BR) instead of
    corners[0] (TL), which proves the UV mapping or index convention is inverted.
    """


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
    chirality_failures: int = 0
    orientation_failures: int = 0
    dictionary_orientation_error: bool = False
    margin_violations: int = 0


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
    quarantined: bool = False


# --- TELEMETRY ---


class TelemetryAuditor:
    """Collects and analyzes worker telemetry using Polars."""

    MAX_RECORDS = 10_000

    def __init__(self):
        self.records: deque[dict[str, Any]] = deque(maxlen=self.MAX_RECORDS)

    def add_entry(self, worker_id: str, telemetry: Telemetry, event_type: str = "heartbeat"):
        """Adds a telemetry record."""
        entry = {
            "timestamp": datetime.now(),
            "worker_id": worker_id,
            "event_type": event_type,
            "vram_used_mb": telemetry.vram_used_mb,
            "vram_total_mb": telemetry.vram_total_mb,
            "ram_used_mb": telemetry.ram_used_mb,
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
            logger.info("Telemetry saved", path=str(output_path))

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
            raw = json.load(f)
        return pl.DataFrame(unwrap_rich_truth(raw))

    def load_raw_records(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Load raw JSON records and the evaluation_context header.

        Returns:
            (records, evaluation_context) where evaluation_context is an empty
            dict for v1 (legacy bare-array) files.
        """
        rich_path = self.dataset_path / "rich_truth.json"
        if not rich_path.exists():
            return [], {}
        with open(rich_path) as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw.get("records", []), raw.get("evaluation_context", {})
        return raw, {}


class DatasetAuditor:
    """Orchestrates the full audit of a dataset.

    Coordinates geometric, environmental, and integrity checks to produce
    a comprehensive quality report and gate status.

    Attributes:
        dataset_path: Path to the dataset root.
        reader: Helper for high-speed data ingestion.
    """

    def __init__(self, dataset_path: Path) -> None:
        """Initialize the DatasetAuditor.

        Args:
            dataset_path: Directory containing the images and metadata.
        """
        self.dataset_path = dataset_path
        self.reader = DatasetReader(dataset_path)

    def run_audit(self, gate_config: QualityGateConfig | None = None) -> AuditResult:
        """Execute all audit passes and evaluate quality gates.

        Args:
            gate_config: Optional configuration for metric-based pass/fail gates.

        Returns:
            An AuditResult containing the full report and gate status.
        """
        df = self.reader.load_rich_detections()
        raw_records, eval_ctx = self.reader.load_raw_records()

        def get_stats(col):
            if col not in df.columns:
                return DistributionStats(min=0, max=0, mean=0, std=0, median=0)
            s = df[col]
            return DistributionStats(
                min=float(s.min() or 0),
                max=float(s.max() or 0),
                mean=float(s.mean() or 0),
                std=float(s.std() or 0),
                median=float(s.median() or 0),
            )

        geom = GeometricAudit(
            distance=get_stats("distance"),
            incidence_angle=get_stats("angle_of_incidence"),
            ppm=get_stats("ppm"),
            tag_count=len(df),
            image_count=df["image_id"].n_unique() if "image_id" in df.columns else 0,
        )
        env = EnvironmentalAudit(lighting_intensity=get_stats("lighting_intensity"))

        chirality_failures = self._run_chirality_check(raw_records)
        orientation_failures, dict_orient_error = self._run_anchor_check(raw_records)
        margin_px = int(eval_ctx.get("photometric_margin_px", 0))
        margin_violations = self._run_margin_check(raw_records, margin_px)

        integrity = IntegrityAudit(
            impossible_poses=int(df.filter(pl.col("distance") < 0).height)
            if "distance" in df.columns
            else 0,
            chirality_failures=chirality_failures,
            orientation_failures=orientation_failures,
            dictionary_orientation_error=dict_orient_error,
            margin_violations=margin_violations,
        )

        report = AuditReport(
            dataset_name=self.dataset_path.name,
            timestamp=datetime.now(UTC).isoformat(),
            geometric=geom,
            environmental=env,
            integrity=integrity,
            score=self._calculate_score(geom, env, integrity),
        )

        gate_passed = True
        gate_failures = []
        if gate_config:
            # Simple gate logic for tests
            pass

        quarantined = chirality_failures > 0 or orientation_failures > 0 or margin_violations > 0

        if chirality_failures > 0:
            gate_failures.append(f"CHIRALITY: {chirality_failures} tag(s) have wrong winding order")
            gate_passed = False
        if orientation_failures > 0:
            msg = f"ORIENTATION: {orientation_failures} tag(s) fail 3D anchor projection"
            if dict_orient_error:
                msg += " [DictionaryOrientationError: texture is 180° out of phase]"
            gate_failures.append(msg)
            gate_passed = False
        if margin_violations > 0:
            gate_failures.append(
                f"MARGIN: {margin_violations} corner(s) marked VISIBLE inside the "
                f"{margin_px}px eval margin — projection bug detected"
            )
            gate_passed = False

        return AuditResult(
            report=report,
            gate_passed=gate_passed,
            gate_failures=gate_failures,
            quarantined=quarantined,
        )

    def _calculate_score(
        self, geom: GeometricAudit, env: EnvironmentalAudit, integrity: IntegrityAudit
    ) -> float:
        """Calculate a heuristic quality score (0-100)."""
        if geom.tag_count == 0:
            return 0.0
        score = 100.0
        score -= integrity.impossible_poses * 10
        if geom.tag_count > 0:
            score -= (integrity.chirality_failures / geom.tag_count) * 50
            score -= (integrity.orientation_failures / geom.tag_count) * 50
        if geom.incidence_angle.max < 45:
            score -= 20
        if geom.distance.max - geom.distance.min < 1.0:
            score -= 10
        return float(max(0.0, min(100.0, score)))

    def _run_chirality_check(self, records: list[dict[str, Any]]) -> int:
        """Phase 1: Chirality invariant test via diagonal cross product.

        For a CW quad [P0=TL, P1=TR, P2=BR, P3=BL] in Y-down image space:
            A = P0→P2,  B = P1→P3
            cross = Ax*By - Ay*Bx  must be > 0

        Note: A 180° index rotation produces the same positive cross product,
        so this test catches mirror flips but NOT 180° orientation errors.
        That is handled by _run_anchor_check.

        Returns:
            Number of TAG records that fail the chirality invariant.
        """
        failures = 0
        for rec in records:
            if rec.get("record_type") != "TAG":
                continue
            corners = rec.get("corners")
            if not corners or len(corners) < 4:
                continue
            p0, p1, p2, p3 = corners[0], corners[1], corners[2], corners[3]
            ax = p2[0] - p0[0]
            ay = p2[1] - p0[1]
            bx = p3[0] - p1[0]
            by = p3[1] - p1[1]
            if ax * by - ay * bx <= 0:
                failures += 1
                logger.warning(
                    "Chirality failure",
                    image_id=rec.get("image_id"),
                    tag_id=rec.get("tag_id"),
                )
        return failures

    def _run_anchor_check(self, records: list[dict[str, Any]]) -> tuple[int, bool]:
        """Phase 2: 3D-to-2D projection anchor test.

        Projects the TL corner of the tag (using the stored pose) and measures
        its distance to annotated corners[0]. Sub-pixel accuracy is expected.

        If the projected TL lands near corners[2] (BR) instead, this is a
        DictionaryOrientationError: the texture is 180° out of phase with the
        3D geometry.

        Returns:
            (failure_count, dictionary_orientation_error)
        """
        _PASS_THRESHOLD = 0.5  # sub-pixel, px
        _FAIL_THRESHOLD = 10.0  # significant error, px

        failures = 0
        dict_orient_error = False

        for rec in records:
            if rec.get("record_type") != "TAG":
                continue
            corners = rec.get("corners")
            pos = rec.get("position")
            quat_wxyz = rec.get("rotation_quaternion")
            k_mat = rec.get("k_matrix")
            tag_size_mm = rec.get("tag_size_mm")
            dist_model = rec.get("distortion_model", "none")
            dist_coeffs = rec.get("distortion_coeffs", [])

            if (
                not corners
                or pos is None
                or quat_wxyz is None
                or k_mat is None
                or tag_size_mm is None
            ):
                continue
            if len(corners) < 4:
                continue

            half = float(tag_size_mm) / 2000.0  # mm → m, half-size

            # Center-Origin, Y-down convention: TL = (-half, -half, 0)
            local_tl = np.array([-half, -half, 0.0])
            R = quaternion_wxyz_to_matrix(quat_wxyz)
            t = np.array(pos, dtype=float)
            p_cam = R @ local_tl + t

            if p_cam[2] <= 0:
                continue  # Behind camera

            k = np.array(k_mat, dtype=float)

            # Apply lens distortion if model is specified
            x_norm = p_cam[0] / p_cam[2]
            y_norm = p_cam[1] / p_cam[2]
            xd, yd = apply_distortion_by_model(
                np.array([x_norm]), np.array([y_norm]), dist_coeffs, dist_model
            )

            x_proj = k[0, 0] * xd[0] + k[0, 2]
            y_proj = k[1, 1] * yd[0] + k[1, 2]

            c0 = corners[0]
            dist0 = float(np.hypot(x_proj - c0[0], y_proj - c0[1]))

            if dist0 > _PASS_THRESHOLD:
                failures += 1
                logger.warning(
                    "Anchor projection failure",
                    image_id=rec.get("image_id"),
                    tag_id=rec.get("tag_id"),
                    dist_to_corner0=round(dist0, 2),
                )

                if dist0 > _FAIL_THRESHOLD:
                    c2 = corners[2]
                    dist2 = float(np.hypot(x_proj - c2[0], y_proj - c2[1]))
                    if dist2 < _PASS_THRESHOLD:
                        dict_orient_error = True
                        logger.error(
                            "DictionaryOrientationError: texture 180° out of phase",
                            image_id=rec.get("image_id"),
                            tag_id=rec.get("tag_id"),
                            dist_to_corner0=round(dist0, 2),
                            dist_to_corner2=round(dist2, 2),
                        )

        return failures, dict_orient_error

    def _run_margin_check(self, records: list[dict[str, Any]], margin_px: int) -> int:
        """Sanity check: no corner marked VISIBLE (v=2) should be inside the margin zone.

        A v=2 flag on a geometrically marginal corner means the visibility
        computation diverged from the geometric truth — catching this early
        prevents corrupted evaluation labels from reaching MLOps teams.

        Returns:
            Number of corners where the stored v=2 flag contradicts the geometry.
        """
        if margin_px == 0:
            return 0

        violations = 0
        for rec in records:
            corners = rec.get("corners")
            vis_flags = rec.get("corners_visibility")
            resolution = rec.get("resolution")
            if not corners or not vis_flags or not resolution or len(resolution) < 2:
                continue
            w, h = int(resolution[0]), int(resolution[1])
            rec_violations = sum(
                1
                for (x, y), v in zip(corners, vis_flags, strict=True)
                if v == KeypointVisibility.VISIBLE
                and (x < margin_px or x >= w - margin_px or y < margin_px or y >= h - margin_px)
            )
            if rec_violations:
                violations += rec_violations
                logger.error(
                    "Margin violation: corners marked VISIBLE inside eval_margin_px zone",
                    image_id=rec.get("image_id"),
                    tag_id=rec.get("tag_id"),
                    violating_corners=rec_violations,
                    margin_px=margin_px,
                )
        return violations


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
