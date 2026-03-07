import fiftyone as fo


def test_oob_detector():
    """Test that out-of-bounds bounding boxes are flagged."""
    from render_tag.viz.fiftyone_tool import check_oob

    # FiftyOne bbox is [rel_x, rel_y, rel_w, rel_h]
    # 1. Valid bbox
    valid_det = fo.Detection(bounding_box=[0.1, 0.1, 0.2, 0.2])
    assert check_oob(valid_det) is False

    # 2. Out of bounds (negative)
    oob_neg = fo.Detection(bounding_box=[-0.1, 0.1, 0.2, 0.2])
    assert check_oob(oob_neg) is True

    # 3. Out of bounds (exceeds 1.0)
    oob_pos = fo.Detection(bounding_box=[0.9, 0.9, 0.2, 0.2])  # x+w = 1.1
    assert check_oob(oob_pos) is True


def test_scale_drift_detector():
    """Test that scale drift (PPM vs bbox area) is flagged."""
    from render_tag.viz.fiftyone_tool import check_scale_drift

    # Scale drift logic: area should be roughly proportional to 1/distance^2
    # or explicitly cross-reference PPM.
    # If PPM is high (close) but area is small, drift!
    # area = w * h * image_area. FiftyOne area is w * h.

    # 1. Consistent: high PPM, large area
    consistent = fo.Detection(bounding_box=[0, 0, 0.5, 0.5])  # area 0.25
    consistent["ppm"] = 100.0
    assert check_scale_drift(consistent) is False

    # 2. Drift: high PPM, tiny area
    drift = fo.Detection(bounding_box=[0, 0, 0.01, 0.01])  # area 0.0001
    drift["ppm"] = 100.0
    assert check_scale_drift(drift) is True
