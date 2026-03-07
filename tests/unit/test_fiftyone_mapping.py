import fiftyone as fo


def test_metadata_hydration_mapping():
    """Test that detection objects are hydrated with custom metadata correctly."""
    from render_tag.viz.fiftyone_tool import hydrate_detection
    
    # Mock detection and rich truth record
    detection = fo.Detection(label="tag36h11")
    record = {
        "distance": 5.0,
        "angle_of_incidence": 45.0,
        "ppm": 100.0,
        "position": [1.0, 2.0, 3.0],
        "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
        "corners": [[0, 0], [10, 0], [10, 10], [0, 10]]
    }
    
    # ACT
    hydrate_detection(detection, record)
    
    # VERIFY
    assert detection["distance"] == 5.0
    assert detection["angle_of_incidence"] == 45.0
    assert detection["ppm"] == 100.0
    assert detection["position"] == [1.0, 2.0, 3.0]
    assert detection["rotation_quaternion"] == [1.0, 0.0, 0.0, 0.0]

def test_keypoint_mapping():
    """Test that corners are mapped to labeled keypoints correctly."""
    from render_tag.viz.fiftyone_tool import map_corners_to_keypoints
    
    corners = [[100, 100], [200, 100], [200, 200], [100, 200]]
    
    # ACT
    keypoints = map_corners_to_keypoints(corners)
    
    # VERIFY
    assert isinstance(keypoints, fo.Keypoints)
    assert len(keypoints.keypoints) == 4
    # Check labels
    labels = [kp.label for kp in keypoints.keypoints]
    assert labels == ["0", "1", "2", "3"]
    # Check points (relative to image size in FiftyOne, but let's assume raw for now 
    # or handle normalization in implementation)
    points = [kp.points[0] for kp in keypoints.keypoints]
    assert points[0] == [100, 100]
