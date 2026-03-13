"""
Unit tests for winding order validation.
"""

import pytest
from pydantic import ValidationError

from render_tag.core.schema import DetectionRecord
from render_tag.generation.projection_math import validate_winding_order


def test_detection_record_valid_winding():
    """Test that DetectionRecord accepts clockwise corners."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # Should not raise
    record = DetectionRecord(image_id="test", tag_id=1, tag_family="tag36h11", corners=corners)
    assert record.corners == corners


def test_detection_record_invalid_winding():
    """Test that DetectionRecord rejects counter-clockwise corners."""
    corners = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
    with pytest.raises(ValidationError) as excinfo:
        DetectionRecord(image_id="test", tag_id=1, tag_family="tag36h11", corners=corners)
    assert "winding" in str(excinfo.value)


def test_detection_record_self_intersecting():
    """Test that DetectionRecord rejects self-intersecting corners."""
    corners = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    with pytest.raises(ValidationError) as excinfo:
        DetectionRecord(image_id="test", tag_id=1, tag_family="tag36h11", corners=corners)
    assert "winding" in str(excinfo.value)


def test_validate_winding_order_clockwise():
    """Test winding order validation for clockwise points."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert validate_winding_order(corners) is True


def test_validate_winding_order_counter_clockwise():
    """Test winding order validation for counter-clockwise points."""
    corners = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
    assert validate_winding_order(corners) is False


def test_validate_winding_order_self_intersecting():
    """Test winding order validation for self-intersecting 'bowtie' polygon."""
    corners = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    assert validate_winding_order(corners) is False


# --- Phase 1: Chirality Invariant (diagonal cross product) ---


def _diagonal_cross(corners):
    """Ax*By - Ay*Bx where A=P0→P2, B=P1→P3."""
    p0, p1, p2, p3 = corners
    ax, ay = p2[0] - p0[0], p2[1] - p0[1]
    bx, by = p3[0] - p1[0], p3[1] - p1[1]
    return ax * by - ay * bx


def test_chirality_cross_product_cw():
    """CW quad in Y-down produces strictly positive cross product of diagonals."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]  # TL TR BR BL
    assert _diagonal_cross(corners) > 0


def test_chirality_cross_product_ccw():
    """CCW (mirrored) quad produces strictly negative cross product."""
    corners = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]  # TL BL BR TR
    assert _diagonal_cross(corners) < 0


def test_chirality_cross_product_mirrored_horizontally():
    """Horizontally mirrored quad (indices go TR→TL→BL→BR) also fails chirality."""
    corners = [(10.0, 0.0), (0.0, 0.0), (0.0, 10.0), (10.0, 10.0)]  # TR TL BL BR
    assert _diagonal_cross(corners) < 0


def test_chirality_cross_product_180_rotation_passes():
    """180° index rotation of a CW quad has the same positive chirality.

    This documents the known limitation: the cross-product test catches mirror
    flips but is BLIND to 180° rotations. That case is handled by the anchor check.
    """
    # BR BL TL TR — same quad, 180° rotated index ordering
    corners = [(10.0, 10.0), (0.0, 10.0), (0.0, 0.0), (10.0, 0.0)]
    assert _diagonal_cross(corners) > 0  # same sign as correct CW — not caught here
