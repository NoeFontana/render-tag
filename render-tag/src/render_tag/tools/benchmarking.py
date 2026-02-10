"""
Performance benchmarking utilities for render-tag.

Provides a context manager and logging helpers to track execution time
and resource usage across different stages of the generation pipeline.
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Performance metrics for a specific pipeline stage."""

    name: str
    duration_sec: float = 0.0
    start_time: float = 0.0


@dataclass
class PerformanceReport:
    """Aggregated performance report for a generation session."""

    session_name: str
    stages: dict[str, StageMetrics] = field(default_factory=dict)

    def add_stage(self, name: str, duration: float):
        self.stages[name] = StageMetrics(name=name, duration_sec=duration)

    def log_summary(self):
        """Log a human-readable summary of the performance metrics."""
        total_time = sum(s.duration_sec for s in self.stages.values())
        logger.info(f"=== Performance Summary: {self.session_name} ===")
        logger.info(f"Total Session Time: {total_time:.3f}s")
        for name, metrics in self.stages.items():
            percentage = (metrics.duration_sec / total_time * 100) if total_time > 0 else 0
            logger.info(f"  - {name:20}: {metrics.duration_sec:8.3f}s ({percentage:5.1f}%)")
        logger.info("==========================================")


class Benchmarker:
    """Manages performance tracking for a generation run."""

    def __init__(self, session_name: str = "Generation"):
        self.report = PerformanceReport(session_name=session_name)

    @contextmanager
    def measure(self, stage_name: str):
        """Context manager to measure the duration of a code block."""
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            self.report.add_stage(stage_name, end - start)

    def get_report(self) -> PerformanceReport:
        return self.report
