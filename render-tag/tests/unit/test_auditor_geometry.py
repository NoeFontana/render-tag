import pytest
import polars as pl
from render_tag.data_io.auditor import GeometryAuditor

def test_geometry_auditor_calculates_stats():
    """Verify that GeometryAuditor calculates basic stats for distance and angle."""
    data = {
        "distance": [1.0, 2.0, 3.0, 4.0, 5.0],
        "angle_of_incidence": [10.0, 20.0, 30.0, 40.0, 50.0],
        "image_id": ["img1", "img1", "img2", "img2", "img3"]
    }
    df = pl.DataFrame(data)
    
    auditor = GeometryAuditor(df)
    results = auditor.audit()
    
    assert results.tag_count == 5
    assert results.image_count == 3
    
    assert results.distance.min == 1.0
    assert results.distance.max == 5.0
    assert results.distance.mean == 3.0
    
    assert results.incidence_angle.min == 10.0
    assert results.incidence_angle.max == 50.0
    assert results.incidence_angle.mean == 30.0
