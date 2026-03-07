import fiftyone as fo


def test_id_label_mapping():
    """
    Test that we can create a labeled keypoint for the tag ID.
    """
    from render_tag.viz.fiftyone_tool import create_id_label

    # Center of tag in normalized coords
    center = [0.5, 0.5]
    tag_id = 42

    # ACT
    kp = create_id_label(center, tag_id)

    # VERIFY
    assert isinstance(kp, fo.Keypoint)
    assert kp.label == "ID: 42"
    assert kp.points[0] == center
