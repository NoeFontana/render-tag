import json

from render_tag.data_io.writers import COCOWriter


def test_coco_writer_keypoints(tmp_path):
    writer = COCOWriter(tmp_path)
    cat_id = writer.add_category("tag36h11")
    img_id = writer.add_image("test.png", 640, 480)

    corners = [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]
    writer.add_annotation(img_id, cat_id, corners)

    output_path = writer.save("coco.json")

    with open(output_path) as f:
        data = json.load(f)

    ann = data["annotations"][0]

    # Check keypoints existence and format
    assert "keypoints" in ann
    assert len(ann["keypoints"]) == 4 * 3  # 4 corners * 3 values (x,y,v)
    assert ann["num_keypoints"] == 4

    # Check category has keypoints metadata
    cat = data["categories"][0]
    assert "keypoints" in cat
    assert len(cat["keypoints"]) == 4
