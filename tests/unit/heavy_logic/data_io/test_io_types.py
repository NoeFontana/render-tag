"""
Unit tests for the centralized types module.
"""

from render_tag.core.schema.base import Corner, DetectionRecord


class TestCorner:
    def test_corner_creation(self) -> None:
        corner = Corner(x=100.5, y=200.5)
        assert corner.x == 100.5
        assert corner.y == 200.5

    def test_corner_as_tuple(self) -> None:
        corner = Corner(x=50.0, y=75.0)
        assert corner.as_tuple() == (50.0, 75.0)


class TestDetectionRecord:
    def test_valid_detection(self) -> None:
        corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
        detection = DetectionRecord(
            image_id="test_image",
            tag_id=42,
            tag_family="tag36h11",
            corners=corners,
        )
        assert detection.is_valid() is True

    def test_invalid_detection_wrong_corners(self) -> None:
        corners = [(0, 0), (100, 0), (100, 100)]  # Only 3 corners
        detection = DetectionRecord(
            image_id="test_image",
            tag_id=42,
            tag_family="tag36h11",
            corners=corners,
        )
        assert detection.is_valid() is False

    def test_to_csv_row(self) -> None:
        corners = [(10.5, 20.5), (110.5, 20.5), (110.5, 120.5), (10.5, 120.5)]
        detection = DetectionRecord(
            image_id="img1", tag_id=5, tag_family="tag36h11", corners=corners
        )
        row = detection.to_csv_row()
        assert row[0] == "img1"
        assert row[3] == "TAG"  # record_type
        assert row[4] == 0.0  # tag_size_mm (default)
        assert row[6] == 10.5  # x1
        assert len(row) == 14  # image_id, tag_id, tag_family, type, size, ppm, x1..y4
