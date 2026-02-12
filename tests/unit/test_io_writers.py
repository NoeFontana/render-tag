"""
Unit tests for the writers module.
"""

import json
import tempfile
from pathlib import Path

from render_tag.data_io.writers import COCOWriter, CSVWriter
from render_tag.schema import DetectionRecord


class TestCSVWriter:
    def test_write_single_detection(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "tags.csv"
        writer = CSVWriter(csv_path)

        corners = [(10.5, 20.5), (110.5, 20.5), (110.5, 120.5), (10.5, 120.5)]
        detection = DetectionRecord(
            image_id="scene_0001",
            tag_id=0,
            tag_family="tag36h11",
            corners=corners,
        )
        writer.write_detection(detection)

        # Read and verify
        content = csv_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # Header + 1 detection
        assert lines[0] == "image_id,tag_id,tag_family,x1,y1,x2,y2,x3,y3,x4,y4"
        assert "scene_0001" in lines[1]
        assert "tag36h11" in lines[1]

    def test_write_multiple_detections(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "tags.csv"
        writer = CSVWriter(csv_path)

        corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
        detections = [
            DetectionRecord(image_id="img1", tag_id=0, tag_family="tag36h11", corners=corners),
            DetectionRecord(image_id="img2", tag_id=1, tag_family="tag36h11", corners=corners),
            DetectionRecord(image_id="img3", tag_id=2, tag_family="DICT_4X4_50", corners=corners),
        ]
        writer.write_detections(detections)

        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == 4  # Header + 3 detections

    def test_skip_invalid_detection(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "tags.csv"
        writer = CSVWriter(csv_path)

        # Invalid detection with only 3 corners
        detection = DetectionRecord(
            image_id="img1", tag_id=0, tag_family="tag36h11", corners=[(0, 0), (1, 1), (2, 2)]
        )
        writer.write_detection(detection)

        # File should not be created since the only detection was invalid
        assert not csv_path.exists()


class TestCOCOWriter:
    def test_add_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = COCOWriter(Path(tmpdir))

            cat_id1 = writer.add_category("tag36h11")
            cat_id2 = writer.add_category("DICT_4X4_50")
            cat_id3 = writer.add_category("tag36h11")  # Duplicate

            assert cat_id1 == 1
            assert cat_id2 == 2
            assert cat_id3 == 1  # Should return existing ID
            assert len(writer.categories) == 2

    def test_add_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = COCOWriter(Path(tmpdir))

            img_id1 = writer.add_image("images/test1.png", 640, 480)
            img_id2 = writer.add_image("images/test2.png", 1920, 1080)

            assert img_id1 == 1
            assert img_id2 == 2
            assert len(writer.images) == 2

    def test_add_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = COCOWriter(Path(tmpdir))

            cat_id = writer.add_category("tag36h11")
            img_id = writer.add_image("test.png", 640, 480)

            corners = [(100, 100), (200, 100), (200, 200), (100, 200)]
            detection = DetectionRecord(
                image_id="test.png", tag_id=5, tag_family="tag36h11", corners=corners
            )
            ann_id = writer.add_annotation(img_id, cat_id, corners, detection=detection)

            assert ann_id == 1
            assert len(writer.annotations) == 1

            ann = writer.annotations[0]
            assert ann["image_id"] == img_id
            assert ann["category_id"] == cat_id
            assert ann["attributes"]["tag_id"] == 5
            assert ann["area"] == 10000.0  # 100x100 square

    def test_save_coco_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            writer = COCOWriter(output_dir)

            cat_id = writer.add_category("tag36h11")
            img_id = writer.add_image("test.png", 640, 480)
            corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
            writer.add_annotation(img_id, cat_id, corners)

            output_path = writer.save()

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "images" in data
            assert "annotations" in data
            assert "categories" in data
            assert len(data["images"]) == 1
            assert len(data["annotations"]) == 1
            assert len(data["categories"]) == 1

    def test_bbox_calculation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = COCOWriter(Path(tmpdir))

            cat_id = writer.add_category("tag36h11")
            img_id = writer.add_image("test.png", 640, 480)

            # Non-axis-aligned quad
            corners = [(50, 100), (150, 50), (200, 150), (100, 200)]
            writer.add_annotation(img_id, cat_id, corners)

            ann = writer.annotations[0]
            bbox = ann["bbox"]

            # bbox = [x_min, y_min, width, height]
            assert bbox[0] == 50  # x_min
            assert bbox[1] == 50  # y_min
            assert bbox[2] == 150  # width (200 - 50)
            assert bbox[3] == 150  # height (200 - 50)
