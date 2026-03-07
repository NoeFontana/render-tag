import numpy as np
import pytest
from render_tag.data_io.annotations import compute_bbox

def test_compute_bbox_strips_invalid_points():
    """
    Test that compute_bbox strips out invalid points (-1e6) 
    and computes the bbox from the remaining valid points.
    """
    # 2 valid points and 2 invalid (behind camera) points
    points = np.array([
        [100.0, 100.0],
        [200.0, 200.0],
        [-1e6, -1e6],
        [-1e6, -1e6]
    ])
    
    bbox = compute_bbox(points)
    
    # Should be computed from [100, 100] and [200, 200]
    # [x_min, y_min, width, height] = [100, 100, 100, 100]
    assert bbox == [100.0, 100.0, 100.0, 100.0]

def test_compute_bbox_zero_on_insufficient_points():
    """
    Test that compute_bbox returns zero box if < 2 points remain.
    """
    points = np.array([
        [100.0, 100.0],
        [-1e6, -1e6],
        [-1e6, -1e6]
    ])
    assert compute_bbox(points) == [0.0, 0.0, 0.0, 0.0]
