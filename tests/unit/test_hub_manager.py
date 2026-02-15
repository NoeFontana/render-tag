import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from scripts.hub_manager import get_dataset_features, render_generator


class TestHubManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for testing
        self.test_dir = Path("tests/tmp/hub_manager_test")
        self.images_dir = self.test_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy image
        self.image_path = self.images_dir / "scene_0001_cam_0001.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(self.image_path)

        # Create corresponding _meta.json
        self.meta_path = self.images_dir / "scene_0001_cam_0001_meta.json"
        self.meta_data = {
            "detections": [
                {
                    "tag_id": 42,
                    "tag_family": "tag36h11",
                    "corners": [[10, 10], [20, 10], [20, 20], [10, 20]],
                    "ppm": 25.0,
                    "distance": 1.5,
                }
            ],
            "provenance": {"git_hash": "deadbeef", "recipe_snapshot": {"scene_id": 1}},
        }
        with open(self.meta_path, "w") as f:
            json.dump(self.meta_data, f)

    def tearDown(self):
        # Clean up temporary files
        if self.test_dir.exists():
            import shutil

            shutil.rmtree(self.test_dir)

    def test_render_generator_success(self):
        """Verify that the generator yields correct records from local files."""
        gen = render_generator(self.test_dir)
        records = list(gen)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["image_id"], "scene_0001_cam_0001")
        self.assertEqual(record["tag_id"], 42)
        self.assertEqual(record["tag_family"], "tag36h11")
        self.assertEqual(float(record["ppm"]), 25.0)

    def test_dataset_schema_integrity(self):
        """Verify that our features match the expected schema."""
        features = get_dataset_features()
        self.assertIn("image", features)
        self.assertIn("ppm", features)
        self.assertIn("corners", features)

    @patch("scripts.hub_manager.Dataset")
    def test_upload_command_flow(self, mock_dataset_class):
        """Mock the Hub interaction to verify the command-line flow."""
        from scripts.hub_manager import upload

        mock_ds = MagicMock()
        mock_dataset_class.from_generator.return_value = mock_ds

        # We need to use a Typer test runner for proper CLI testing,
        # but here we test the function directly for logic verification
        upload(
            data_dir=self.test_dir, repo_id="test/repo", config_name="test_config", dry_run=False
        )

        # Verify push_to_hub was called with correct config
        mock_ds.push_to_hub.assert_called_once()
        _, kwargs = mock_ds.push_to_hub.call_args
        self.assertEqual(kwargs["config_name"], "test_config")
        self.assertEqual(kwargs["repo_id"], "test/repo")

    @patch("scripts.hub_manager.load_dataset")
    def test_download_restoration(self, mock_load_dataset):
        """Verify that download restores local files correctly."""
        from scripts.hub_manager import download

        # Mock record from Hub
        mock_record = {
            "image": Image.new("RGB", (10, 10)),
            "image_id": "scene_9999_cam_0000",
            "tag_id": 1,
            "tag_family": "tag16h5",
            "corners": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "distance": 1.0,
            "angle_of_incidence": 0.0,
            "pixel_area": 100.0,
            "occlusion_ratio": 0.0,
            "ppm": 10.0,
            "position": [0, 0, 1],
            "rotation_quaternion": [1, 0, 0, 0],
            "metadata": "{}",
        }
        mock_load_dataset.return_value = [mock_record]

        out_dir = self.test_dir / "restored"
        download(repo_id="test/repo", output_dir=out_dir)

        # Verify files exist
        images_dir = out_dir / "images"
        self.assertTrue((images_dir / "scene_9999_cam_0000.png").exists())
        self.assertTrue((images_dir / "scene_9999_cam_0000_meta.json").exists())

        # Verify content of restored meta
        with open(images_dir / "scene_9999_cam_0000_meta.json") as f:
            restored_meta = json.load(f)
            self.assertEqual(len(restored_meta["detections"]), 1)
            self.assertEqual(restored_meta["detections"][0]["tag_id"], 1)
            self.assertTrue(restored_meta["provenance"]["restored_from_hub"])


if __name__ == "__main__":
    unittest.main()
