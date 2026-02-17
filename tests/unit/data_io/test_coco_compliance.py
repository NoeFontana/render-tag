
import json
import pytest
from pathlib import Path
from render_tag.data_io.writers import COCOWriter
from render_tag.core.schema.base import DetectionRecord

def test_coco_keypoint_compliance_tag(tmp_path):
    writer = COCOWriter(tmp_path)
    
    det = DetectionRecord(
        image_id="img1",
        tag_id=1,
        tag_family="tag36h11",
        corners=[(10, 10), (20, 10), (20, 20), (10, 20)],
        record_type="TAG"
    )
    
    cat_id = writer.add_category("tag36h11")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, det.corners, detection=det)
    
    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)
    
    ann = data["annotations"][0]
    # COCO Keypoints: [x1, y1, v1, x2, y2, v2, ...]
    # v=2 means visible and labeled
    assert len(ann["keypoints"]) == 4 * 3
    assert ann["num_keypoints"] == 4
    for i in range(4):
        assert ann["keypoints"][i*3 + 2] == 2

def test_coco_keypoint_compliance_subject(tmp_path):
    writer = COCOWriter(tmp_path)
    
    # Subject with 4 corners and 2 extra keypoints (e.g. saddle points)
    det = DetectionRecord(
        image_id="img1",
        tag_id=0,
        tag_family="board",
        corners=[(0, 0), (100, 0), (100, 100), (0, 100)],
        keypoints=[(50, 50), (60, 60)],
        record_type="SUBJECT"
    )
    
    cat_id = writer.add_category("board")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, det.corners, detection=det)
    
    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)
    
    ann = data["annotations"][0]
    # 4 corners + 2 keypoints = 6 total
    assert len(ann["keypoints"]) == 6 * 3
    assert ann["num_keypoints"] == 6
    assert ann["attributes"]["record_type"] == "SUBJECT"

def test_coco_single_point_box(tmp_path):
    writer = COCOWriter(tmp_path)
    
    # Only one point (e.g. a single saddle point record if we exported that way)
    # COCOWriter handles < 3 points by creating a tiny box
    corners = [(50.0, 50.0)]
    
    cat_id = writer.add_category("point")
    img_id = writer.add_image("img1.png", 640, 480)
    writer.add_annotation(img_id, cat_id, corners)
    
    output_path = writer.save()
    with open(output_path) as f:
        data = json.load(f)
    
    ann = data["annotations"][0]
    # Bbox: [x, y, w, h]
    # For single point at (50, 50), box should be [49.5, 49.5, 1.0, 1.0]
    assert ann["bbox"] == [49.5, 49.5, 1.0, 1.0]
    assert ann["area"] == 1.0
