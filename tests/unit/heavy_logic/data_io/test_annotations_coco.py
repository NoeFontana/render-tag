import numpy as np

from render_tag.data_io.annotations import format_coco_keypoints


def test_format_coco_keypoints_all_visible():
    # 4 points, all visible
    points = np.array([[10, 10], [20, 10], [20, 20], [10, 20]])
    visibility = np.array([True, True, True, True])

    keypoints = format_coco_keypoints(points, visibility)

    assert keypoints == [10.0, 10.0, 2, 20.0, 10.0, 2, 20.0, 20.0, 2, 10.0, 20.0, 2]


def test_format_coco_keypoints_some_occluded():
    points = np.array([[10, 10], [20, 10], [20, 20], [10, 20]])
    visibility = np.array([True, False, True, False])

    keypoints = format_coco_keypoints(points, visibility)

    # Visible = 2, Occluded (but labeled) = 1
    # Assuming we treat occluded as "labeled but not visible"
    assert keypoints == [10.0, 10.0, 2, 20.0, 10.0, 1, 20.0, 20.0, 2, 10.0, 20.0, 1]


def test_format_coco_keypoints_empty():
    keypoints = format_coco_keypoints(np.array([]), np.array([]))
    assert keypoints == []


def test_format_coco_keypoints_sentinel_maps_to_v0():
    """Sentinel (-1, -1) with visibility=False must produce COCO v=0."""
    points = np.array([[10, 10], [-1, -1], [20, 20], [-1, -1]])
    visibility = np.array([True, False, True, False])

    keypoints = format_coco_keypoints(points, visibility)

    # Visible → v=2, sentinel → v=0 with zeroed coords, occluded non-sentinel → v=1
    assert keypoints == [10.0, 10.0, 2, 0.0, 0.0, 0, 20.0, 20.0, 2, 0.0, 0.0, 0]


def test_format_coco_keypoints_occluded_non_sentinel():
    """Non-sentinel points with visibility=False must produce COCO v=1."""
    points = np.array([[10, 10], [50, 60]])
    visibility = np.array([True, False])

    keypoints = format_coco_keypoints(points, visibility)

    assert keypoints == [10.0, 10.0, 2, 50.0, 60.0, 1]
