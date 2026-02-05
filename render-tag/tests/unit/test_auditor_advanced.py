import pytest
import polars as pl
from render_tag.data_io.auditor import EnvironmentalAuditor, IntegrityAuditor

def test_environmental_auditor_stats():
    """Verify that EnvironmentalAuditor calculates lighting stats."""
    data = {
        "lighting_intensity": [10.0, 20.0, 30.0],
        "image_id": ["img1", "img2", "img3"]
    }
    df = pl.DataFrame(data)
    
    auditor = EnvironmentalAuditor(df)
    results = auditor.audit()
    
    assert results.lighting_intensity.min == 10.0
    assert results.lighting_intensity.max == 30.0
    assert results.lighting_intensity.mean == 20.0

def test_integrity_auditor_impossible_poses():
    """Verify that IntegrityAuditor detects tags behind camera (z < 0)."""
    # In our rich metadata, distance is usually positive. 
    # Let's assume we add a 'z_depth' or similar if we want to catch bugs.
    # For now, we can use distance < 0 as a sanity check if it ever happens.
    data = {
        "distance": [-1.0, 2.0, 5.0],
        "image_id": ["img1", "img2", "img3"]
    }
    df = pl.DataFrame(data)
    
    auditor = IntegrityAuditor(df)
    results = auditor.audit()
    
    assert results.impossible_poses == 1
