"""
Unit tests for the schemas module.
"""

import pytest

from render_tag.schemas import (
    COCOAnnotation,
    COCOCategory,
    COCODataset,
    COCOImage,
    Corner,
    TagDetection,
)


class TestCorner:
    def test_corner_creation(self) -> None:
        corner = Corner(x=100.5, y=200.5)
        assert corner.x == 100.5
        assert corner.y == 200.5

    def test_corner_as_tuple(self) -> None:
        corner = Corner(x=50.0, y=75.0)
        assert corner.as_tuple() == (50.0, 75.0)


class TestTagDetection:
    def test_valid_detection(self) -> None:
        corners = [Corner(0, 0), Corner(100, 0), Corner(100, 100), Corner(0, 100)]
        detection = TagDetection(
            image_id="test_001",
            tag_id=42,
            tag_family="tag36h11",
            corners=corners,
        )
        assert detection.image_id == "test_001"
        assert detection.tag_id == 42
        assert len(detection.corners) == 4

    def test_invalid_corner_count(self) -> None:
        corners = [Corner(0, 0), Corner(100, 0), Corner(100, 100)]  # Only 3
        with pytest.raises(ValueError, match="exactly 4 corners"):
            TagDetection(
                image_id="test_001",
                tag_id=0,
                corners=corners,
            )

    def test_empty_corners_allowed(self) -> None:
        detection = TagDetection(image_id="test_001", tag_id=0)
        assert len(detection.corners) == 0

    def test_to_csv_row(self) -> None:
        corners = [
            Corner(10.5, 20.5),
            Corner(110.5, 20.5),
            Corner(110.5, 120.5),
            Corner(10.5, 120.5),
        ]
        detection = TagDetection(
            image_id="img_001",
            tag_id=5,
            tag_family="DICT_4X4_50",
            corners=corners,
        )
        row = detection.to_csv_row()
        
        assert row[0] == "img_001"
        assert row[1] == 5
        assert row[2] == "DICT_4X4_50"
        assert row[3] == 10.5  # x1
        assert row[4] == 20.5  # y1
        assert len(row) == 11  # image_id, tag_id, tag_family, 4 x 2 coords

    def test_csv_header(self) -> None:
        header = TagDetection.csv_header()
        assert header == ["image_id", "tag_id", "tag_family", "x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"]


class TestCOCOImage:
    def test_coco_image_creation(self) -> None:
        img = COCOImage(id=1, file_name="test.png", width=640, height=480)
        assert img.id == 1
        assert img.file_name == "test.png"
        assert img.width == 640
        assert img.height == 480


class TestCOCOCategory:
    def test_default_supercategory(self) -> None:
        cat = COCOCategory(id=1, name="tag36h11")
        assert cat.supercategory == "fiducial_marker"

    def test_custom_supercategory(self) -> None:
        cat = COCOCategory(id=1, name="tag36h11", supercategory="apriltag")
        assert cat.supercategory == "apriltag"


class TestCOCOAnnotation:
    def test_annotation_creation(self) -> None:
        ann = COCOAnnotation(
            id=1,
            image_id=1,
            category_id=1,
            segmentation=[[0, 0, 100, 0, 100, 100, 0, 100]],
            bbox=[0, 0, 100, 100],
            area=10000.0,
        )
        assert ann.id == 1
        assert ann.iscrowd == 0

    def test_to_dict(self) -> None:
        ann = COCOAnnotation(
            id=1,
            image_id=2,
            category_id=3,
            segmentation=[[0, 0, 100, 0, 100, 100, 0, 100]],
            bbox=[0, 0, 100, 100],
            area=10000.0,
        )
        d = ann.to_dict()
        
        assert d["id"] == 1
        assert d["image_id"] == 2
        assert d["category_id"] == 3
        assert d["area"] == 10000.0
        assert d["iscrowd"] == 0


class TestCOCODataset:
    def test_empty_dataset(self) -> None:
        dataset = COCODataset()
        assert len(dataset.images) == 0
        assert len(dataset.annotations) == 0
        assert len(dataset.categories) == 0

    def test_dataset_to_dict(self) -> None:
        dataset = COCODataset(
            images=[COCOImage(id=1, file_name="test.png", width=640, height=480)],
            categories=[COCOCategory(id=1, name="tag36h11")],
            annotations=[
                COCOAnnotation(
                    id=1,
                    image_id=1,
                    category_id=1,
                    segmentation=[[0, 0, 100, 0, 100, 100, 0, 100]],
                    bbox=[0, 0, 100, 100],
                    area=10000.0,
                )
            ],
        )
        
        d = dataset.to_dict()
        
        assert "images" in d
        assert "annotations" in d
        assert "categories" in d
        assert len(d["images"]) == 1
        assert len(d["annotations"]) == 1
        assert len(d["categories"]) == 1
        assert d["images"][0]["file_name"] == "test.png"
