"""
Telemetry auditing and analysis tool using Polars.
"""

import logging
import polars as pl
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from render_tag.schema.hot_loop import Telemetry

logger = logging.getLogger(__name__)

class TelemetryAuditor:
    """
    Collects and analyzes worker telemetry using Polars DataFrames.
    """

    def __init__(self):
        self.records: List[Dict[str, Any]] = []

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
            "state_hash": telemetry.state_hash
        }
        self.records.append(entry)

    def get_dataframe(self) -> pl.DataFrame:
        """Returns the collected records as a Polars DataFrame."""
        if not self.records:
            return pl.DataFrame()
        return pl.DataFrame(self.records)

    def save_csv(self, output_path: Path):
        """Saves the telemetry to a CSV file."""
        df = self.get_dataframe()
        if not df.is_empty():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.write_csv(output_path)
            logger.info(f"Telemetry saved to {output_path}")

    def analyze_throughput(self) -> Dict[str, Any]:
        """Calculates throughput statistics."""
        df = self.get_dataframe()
        if df.is_empty():
            return {}

        # Filter for render completion events if we had them
        # For now, just analyze general activity
        duration = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()
        total_events = len(df)
        
        return {
            "total_duration_sec": duration,
            "event_count": total_events,
            "avg_vram_mb": df["vram_used_mb"].mean(),
            "max_vram_mb": df["vram_used_mb"].max(),
        }
