"""
Interactive HTML Dashboard Generator for Dataset Auditing.
"""

from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import polars as pl

from .auditor_schema import AuditResult
from .auditor import DatasetReader

class DashboardGenerator:
    """Generates a standalone HTML dashboard from an AuditResult."""

    def __init__(self, dataset_path: Path, result: AuditResult) -> None:
        self.dataset_path = dataset_path
        self.result = result
        self.reader = DatasetReader(dataset_path)

    def generate(self, filename: str = "audit_dashboard.html") -> Path:
        """Generate the HTML dashboard.

        Args:
            filename: Output filename.

        Returns:
            Path to the generated HTML file.
        """
        # Load raw data for histograms
        df = self.reader.load_rich_detections()
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Distance Distribution", "Incidence Angle Distribution", 
                            "Lighting Intensity", "Summary Stats"),
            vertical_spacing=0.15,
            specs=[[{"type": "histogram"}, {"type": "histogram"}],
                   [{"type": "histogram"}, {"type": "table"}]]
        )

        # 1. Distance Histogram
        if "distance" in df.columns:
            fig.add_trace(
                go.Histogram(x=df["distance"], name="Distance (m)", nbinsx=30),
                row=1, col=1
            )

        # 2. Angle Histogram
        if "angle_of_incidence" in df.columns:
            fig.add_trace(
                go.Histogram(x=df["angle_of_incidence"], name="Angle (deg)", nbinsx=30),
                row=1, col=2
            )

        # 3. Lighting Intensity Histogram
        if "lighting_intensity" in df.columns:
            fig.add_trace(
                go.Histogram(x=df["lighting_intensity"], name="Lighting Int.", nbinsx=20),
                row=2, col=1
            )

        # 4. Summary Table
        report = self.result.report
        fig.add_trace(
            go.Table(
                header=dict(values=['Metric', 'Value'],
                            fill_color='paleturquoise',
                            align='left'),
                cells=dict(values=[
                    ['Score', 'Status', 'Tags', 'Images', 'Impossible Poses'],
                    [f"{report.score:.1f}/100", 
                     "PASSED" if self.result.gate_passed else "FAILED",
                     report.geometric.tag_count,
                     report.geometric.image_count,
                     report.integrity.impossible_poses]
                ],
                fill_color='lavender',
                align='left')
            ),
            row=2, col=2
        )

        # Update layout
        fig.update_layout(
            height=900, 
            width=1200,
            title_text=f"AUDIT REPORT: {self.dataset_path.name}",
            showlegend=False
        )

        output_path = self.dataset_path / filename
        fig.write_html(str(output_path))
        
        return output_path
