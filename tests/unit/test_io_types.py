"""
Unit tests for the centralized types module.
"""

from render_tag.data_io.types import Corner, DetectionRecord


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
        assert detection.validate() is True

    def test_invalid_detection_wrong_corners(self) -> None:
        corners = [(0, 0), (100, 0), (100, 100)]  # Only 3 corners
        detection = DetectionRecord(
            image_id="test_image",
            tag_id=42,
            tag_family="tag36h11",
            corners=corners,
        )
        assert detection.validate() is False

    def test_to_csv_row(self) -> None:
        corners = [(10.5, 20.5), (110.5, 20.5), (110.5, 120.5), (10.5, 120.5)]
        detection = DetectionRecord("img1", 5, "tag36h11", corners)
        row = detection.to_csv_row()
        assert row[0] == "img1"
        assert row[3] == 10.5
        assert len(row) == 11
