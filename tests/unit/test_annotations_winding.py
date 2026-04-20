from render_tag.core.geometry.projection_math import validate_winding_order
from render_tag.data_io.annotations import verify_corner_order


def test_winding_order_consistency():
    """
    Both layers must agree: [TL, TR, BR, BL] in Y-down image space is
    Clockwise (positive signed area).
    """
    # 0,0 --- 1,0
    #  |       |
    # 0,1 --- 1,1
    cw_corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    assert validate_winding_order(cw_corners) is True, (
        "projection_math should consider [TL,TR,BR,BL] CW (Positive Area)"
    )
    assert verify_corner_order(cw_corners, "cw") is True, (
        "annotations should agree: [TL,TR,BR,BL] is CW (Positive Area)"
    )


def test_ccw_consistency():
    """
    Both layers must agree: [TL, BL, BR, TR] in Y-down image space is
    Counter-Clockwise (negative signed area).
    """
    # 0,0 --- 1,0
    #  |       |
    # 0,1 --- 1,1
    ccw_corners = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]

    assert validate_winding_order(ccw_corners) is False, (
        "projection_math should NOT consider [TL,BL,BR,TR] CW (Negative Area)"
    )
    assert verify_corner_order(ccw_corners, "ccw") is True, (
        "annotations should recognize [TL,BL,BR,TR] as CCW (Negative Area)"
    )
