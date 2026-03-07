from __future__ import annotations

import numpy as np
import pytest

from render_tag.data_io.annotations import verify_corner_order
from render_tag.generation.projection_math import validate_winding_order


def test_winding_order_contradiction():
    """
    Test that annotations.verify_corner_order matches projection_math.validate_winding_order.
    In Y-down coordinate systems (OpenCV):
    - Positive Area = Clockwise (CW)
    """
    # Corners in Clockwise order (Y-down)
    # (0,0) -> (1,0) -> (1,1) -> (0,1)
    # TL -> TR -> BR -> BL
    cw_corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    # 1. Check projection_math (The mathematical truth we want to standardize on)
    assert validate_winding_order(cw_corners) is True, "projection_math should consider this CW (Positive Area)"

    # 2. Check annotations.verify_corner_order (Currently contradictory)
    # It SHOULD return True for "cw", but it currently returns False because it expects negative area for CW.
    assert verify_corner_order(cw_corners, "cw") is True, "annotations should consider this CW (Positive Area)"


def test_ccw_winding_order():
    """
    Test Counter-Clockwise (CCW) order in Y-down.
    - Negative Area = Counter-Clockwise (CCW)
    """
    # Corners in Counter-Clockwise order (Y-down)
    # (0,0) -> (0,1) -> (1,1) -> (1,0)
    # TL -> BL -> BR -> TR
    ccw_corners = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]

    # 1. Check projection_math (Standard logic: CCW is NOT CW)
    assert validate_winding_order(ccw_corners) is False, "projection_math should NOT consider this CW (Negative Area)"

    # 2. Check annotations.verify_corner_order
    # It SHOULD return True for "ccw", but it currently returns True because it expects positive area for CCW.
    # Wait, if signed_area is negative for CCW, then verify_corner_order(ccw_corners, "ccw") will return False.
    # Let's verify signed_area for CCW:
    # x = [0, 0, 1, 1], y = [0, 1, 1, 0]
    # y_roll = [1, 1, 0, 0]
    # signed_area = 0.5 * (0*1 + 0*1 + 1*0 + 1*0 - (0*0 + 1*0 + 1*1 + 0*1))
    # signed_area = 0.5 * (0 - 1) = -0.5.
    # verify_corner_order(ccw_corners, "ccw") currently returns signed_area > 0 -> False.
    # So it's failing to recognize CCW as CCW as well (if we define CCW as Negative Area).
    assert verify_corner_order(ccw_corners, "ccw") is True, "annotations should consider this CCW (Negative Area)"
