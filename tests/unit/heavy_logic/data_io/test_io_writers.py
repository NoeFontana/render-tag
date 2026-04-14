"""
Unit tests for the writers module.
"""

import json
from pathlib import Path

from render_tag.core.schema.base import DetectionRecord, KeypointVisibility
from render_tag.data_io.writers import COCOWriter, CSVWriter, RichTruthWriter, merge_coco_shards


class TestCSVWriter:
    def test_write_single_detection(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "tags.csv"
        with CSVWriter(csv_path) as writer:
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
        expected_header = (
            "image_id,tag_id,tag_family,record_type,tag_size_mm,ppm,"
            "is_mirrored,x1,y1,x2,y2,x3,y3,x4,y4"
        )
        assert lines[0] == expected_header
        assert "scene_0001" in lines[1]
        assert "tag36h11" in lines[1]

    def test_write_multiple_detections(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "tags.csv"
        with CSVWriter(csv_path) as writer:
            corners = [(0, 0), (100, 0), (100, 100), (0, 100)]
            detections = [
                DetectionRecord(image_id="img1", tag_id=0, tag_family="tag36h11", corners=corners),
                DetectionRecord(image_id="img2", tag_id=1, tag_family="tag36h11", corners=corners),
                DetectionRecord(
                    image_id="img3", tag_id=2, tag_family="DICT_4X4_50", corners=corners
                ),
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
        writer.close()

        # File should not be created since the only detection was invalid
        assert not csv_path.exists()


class TestCOCOWriter:
    def test_add_category(self, tmp_path: Path) -> None:
        writer = COCOWriter(tmp_path)

        cat_id1 = writer.add_category("tag36h11")
        cat_id2 = writer.add_category("DICT_4X4_50")
        cat_id3 = writer.add_category("tag36h11")  # Duplicate

        assert cat_id1 == 1
        assert cat_id2 == 2
        assert cat_id3 == 1  # Should return existing ID
        assert len(writer.categories) == 2

    def test_add_image(self, tmp_path: Path) -> None:
        writer = COCOWriter(tmp_path)

        img_id1 = writer.add_image("images/test1.png", 640, 480)
        img_id2 = writer.add_image("images/test2.png", 1920, 1080)

        assert img_id1 == 1
        assert img_id2 == 2
        assert len(writer.images) == 2

    def test_add_annotation(self, tmp_path: Path) -> None:
        writer = COCOWriter(tmp_path)

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

    def test_save_coco_json(self, tmp_path: Path) -> None:
        output_dir = tmp_path
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

    def test_bbox_calculation(self, tmp_path: Path) -> None:
        writer = COCOWriter(tmp_path)

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


class TestRichTruthWriter:
    def _make_det(self, corners, resolution=(640, 480), keypoints=None):
        return DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            corners=corners,
            resolution=list(resolution),
            keypoints=keypoints,
        )

    def test_versioned_envelope(self, tmp_path):
        """Output is a wrapped object with version and evaluation_context."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json")
        writer.add_detection(self._make_det([(10, 10), (100, 10), (100, 100), (10, 100)]))
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        assert data["version"] == "2.0"
        assert "evaluation_context" in data
        assert data["evaluation_context"]["photometric_margin_px"] == 0
        assert "records" in data
        assert len(data["records"]) == 1

    def test_visibility_flags_written_with_margin(self, tmp_path):
        """Corners inside the margin zone get v=1; interior corners get v=2."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=20)
        # corners[0] and [1] are inside the 20px top margin; [2] and [3] are interior
        det = self._make_det(
            corners=[(10, 10), (630, 10), (630, 470), (10, 470)],
            resolution=(640, 480),
        )
        writer.add_detection(det)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        rec = data["records"][0]
        assert "corners_visibility" in rec
        vis = rec["corners_visibility"]
        assert len(vis) == 4
        assert vis[0] == KeypointVisibility.MARGIN_TRUNCATED  # (10,10) — both axes in margin
        assert vis[1] == KeypointVisibility.MARGIN_TRUNCATED  # (630,10) — top margin
        assert vis[2] == KeypointVisibility.MARGIN_TRUNCATED  # (630,470) — right+bottom margin
        assert vis[3] == KeypointVisibility.MARGIN_TRUNCATED  # (10,470) — left+bottom margin

    def test_interior_corners_visible(self, tmp_path):
        """Corners well inside the image with margin are marked VISIBLE."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=10)
        det = self._make_det(
            corners=[(50, 50), (590, 50), (590, 430), (50, 430)],
            resolution=(640, 480),
        )
        writer.add_detection(det)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        vis = data["records"][0]["corners_visibility"]
        assert all(v == KeypointVisibility.VISIBLE for v in vis)

    def test_no_margin_all_visible(self, tmp_path):
        """With eval_margin_px=0 all non-sentinel in-image corners are VISIBLE."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=0)
        det = self._make_det(
            corners=[(1, 1), (639, 1), (639, 479), (1, 479)],
            resolution=(640, 480),
        )
        writer.add_detection(det)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        vis = data["records"][0]["corners_visibility"]
        assert all(v == KeypointVisibility.VISIBLE for v in vis)

    def test_no_resolution_no_visibility(self, tmp_path):
        """Records without a resolution field have corners_visibility serialized as null."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=10)
        det = DetectionRecord(
            image_id="img1",
            tag_id=1,
            tag_family="tag36h11",
            corners=[(10, 10), (100, 10), (100, 100), (10, 100)],
            # resolution intentionally omitted
        )
        writer.add_detection(det)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        assert data["records"][0]["corners_visibility"] is None

    def test_evaluation_context_records_margin(self, tmp_path):
        """eval_margin_px is surfaced in the evaluation_context header."""
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=15)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        assert data["evaluation_context"]["photometric_margin_px"] == 15
        assert data["evaluation_context"]["truncation_policy"] == "ternary_visibility"

    def test_margin_propagation_from_record(self, tmp_path: Path):
        """RichTruthWriter should prefer the margin from the DetectionRecord if provided."""
        # Initialized with margin 0
        writer = RichTruthWriter(tmp_path / "rich_truth.json", eval_margin_px=0)

        # Record has margin 21
        det = self._make_det(
            corners=[(10, 10), (100, 10), (100, 100), (10, 100)],
            resolution=(640, 480),
        )
        det.eval_margin_px = 21

        writer.add_detection(det)
        writer.save()

        with open(tmp_path / "rich_truth.json") as f:
            data = json.load(f)

        # Global header should now reflect the 21px margin from the record
        assert data["evaluation_context"]["photometric_margin_px"] == 21
        # Corner visibility should have used 21px (so (10,10) is MARGIN_TRUNCATED)
        assert data["records"][0]["corners_visibility"][0] == KeypointVisibility.MARGIN_TRUNCATED


class TestShardMerge:
    def test_merge_coco_shards_is_atomic(self, tmp_path: Path) -> None:
        """Merged output must not leave partial files on disk."""
        # Create two shard files
        shard_1 = {
            "images": [{"id": 1, "file_name": "a.png", "width": 640, "height": 480}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1}],
            "categories": [{"id": 1, "name": "tag36h11"}],
        }
        shard_2 = {
            "images": [{"id": 1, "file_name": "b.png", "width": 640, "height": 480}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1}],
            "categories": [{"id": 1, "name": "tag36h11"}],
        }
        for i, shard in enumerate([shard_1, shard_2]):
            with open(tmp_path / f"coco_shard_{i}.json", "w") as f:
                json.dump(shard, f)

        merge_coco_shards(tmp_path, cleanup=False)

        final_path = tmp_path / "coco_labels.json"
        assert final_path.exists()
        # No .tmp file should remain
        assert not final_path.with_suffix(".tmp").exists()

        with open(final_path) as f:
            merged = json.load(f)

        assert len(merged["images"]) == 2
        assert len(merged["annotations"]) == 2
        # IDs should be re-mapped to avoid collisions
        image_ids = [img["id"] for img in merged["images"]]
        assert len(set(image_ids)) == 2  # unique IDs
