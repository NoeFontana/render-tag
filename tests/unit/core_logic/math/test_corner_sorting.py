"""
Unit tests for winding order validation.
"""

import numpy as np
import pytest

from render_tag.generation.projection_math import validate_winding_order
from render_tag.core.schema import DetectionRecord
from pydantic import ValidationError

def test_detection_record_valid_winding():
    """Test that DetectionRecord accepts clockwise corners."""
    corners = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0)
    ]
    # Should not raise
    record = DetectionRecord(
        image_id="test",
        tag_id=1,
        tag_family="tag36h11",
        corners=corners
    )
    assert record.corners == corners

def test_detection_record_invalid_winding():
    """Test that DetectionRecord rejects counter-clockwise corners."""
    corners = [
        (0.0, 0.0),
        (0.0, 10.0),
        (10.0, 10.0),
        (10.0, 0.0)
    ]
    with pytest.raises(ValidationError) as excinfo:
        DetectionRecord(
            image_id="test",
            tag_id=1,
            tag_family="tag36h11",
            corners=corners
        )
    assert "winding" in str(excinfo.value)

def test_detection_record_self_intersecting():
    """Test that DetectionRecord rejects self-intersecting corners."""
    corners = [
        (0.0, 0.0),
        (10.0, 10.0),
        (10.0, 0.0),
        (0.0, 10.0)
    ]
    with pytest.raises(ValidationError) as excinfo:
        DetectionRecord(
            image_id="test",
            tag_id=1,
            tag_family="tag36h11",
            corners=corners
        )
    assert "winding" in str(excinfo.value)

def test_validate_winding_order_clockwise():
    """Test winding order validation for clockwise points."""
    corners = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0)
    ]
    assert validate_winding_order(corners) is True

def test_validate_winding_order_counter_clockwise():
    """Test winding order validation for counter-clockwise points."""
    corners = [
        (0.0, 0.0),
        (0.0, 10.0),
        (10.0, 10.0),
        (10.0, 0.0)
    ]
    assert validate_winding_order(corners) is False

def test_validate_winding_order_self_intersecting():
    """Test winding order validation for self-intersecting 'bowtie' polygon."""
    corners = [
        (0.0, 0.0),
        (10.0, 10.0),
        (10.0, 0.0),
        (0.0, 10.0)
    ]
    assert validate_winding_order(corners) is False
