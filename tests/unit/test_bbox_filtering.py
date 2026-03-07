import numpy as np
import pytest
from render_tag.data_io.annotations import compute_bbox

def test_compute_bbox_with_invalid_points():
    """
    Test that compute_bbox incorrectly includes -1e6 points, 
    resulting in a massive bounding box.
    """
    # 2 valid points and 2 invalid (behind camera) points
    points = np.array([
        [100.0, 100.0],
        [200.0, 200.0],
        [-1e6, -1e6],
        [-1e6, -1e6]
    ])
    
    bbox = compute_bbox(points)
    
    # NEW implementation should return [0,0,0,0]
    assert bbox == [0.0, 0.0, 0.0, 0.0]

def test_compute_bbox_strict_filtering():
    """
    Placeholder for the NEW compute_bbox behavior.
    If ANY corner is -1e6, it should return [0,0,0,0].
    """
    pass
