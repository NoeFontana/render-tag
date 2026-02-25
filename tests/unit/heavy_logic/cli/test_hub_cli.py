import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from render_tag.cli.hub import get_dataset_features, render_generator


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

    def test_render_generator_from_rich_truth(self):
        """Verify that generator yields records from rich_truth.json in new benchmark structure."""
        # Create rich_truth.json structure
        rich_truth_path = self.test_dir / "rich_truth.json"
        rich_truth_data = [
            {
                "image_id": "scene_0001_cam_0001",
                "tag_id": 42,
                "tag_family": "tag36h11",
                "record_type": "TAG",
                "corners": [[10.0, 10.0], [20.0, 10.0], [20.0, 20.0], [10.0, 20.0]],
                "keypoints": None,
                "distance": 1.5,
                "angle_of_incidence": 0.0,
                "pixel_area": 0.0,
                "occlusion_ratio": 0.0,
                "ppm": 25.0,
                "position": [0.0, 0.0, 1.5],
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                "metadata": {}
            }
        ]
        with open(rich_truth_path, "w") as f:
            json.dump(rich_truth_data, f)
            
        # Overwrite the existing _meta.json with new recipe snapshot structure (no detections)
        self.meta_data = {
            "git_hash": "deadbeef",
            "recipe_snapshot": {"scene_id": 1}
        }
        with open(self.meta_path, "w") as f:
            json.dump(self.meta_data, f)

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

    @patch("render_tag.cli.hub.Dataset")
    def test_upload_command_flow(self, mock_dataset_class):
        """Mock the Hub interaction to verify the command-line flow."""
        from render_tag.cli.hub import push_dataset

        mock_ds = MagicMock()
        mock_dataset_class.from_generator.return_value = mock_ds

        # We need to use a Typer test runner for proper CLI testing,
        # but here we test the function directly for logic verification
        push_dataset(
            data_dir=self.test_dir, repo_id="test/repo", config_name="test_config", dry_run=False
        )

        # Verify push_to_hub was called with correct config
        mock_ds.push_to_hub.assert_called_once()
        _, kwargs = mock_ds.push_to_hub.call_args
        self.assertEqual(kwargs["config_name"], "test_config")
        self.assertEqual(kwargs["repo_id"], "test/repo")

    @patch("render_tag.cli.hub.load_dataset")
    def test_download_restoration(self, mock_load_dataset):
        """Verify that download restores local files correctly."""
        from render_tag.cli.hub import pull_dataset

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
        pull_dataset(repo_id="test/repo", output_dir=out_dir)

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

    @patch("render_tag.cli.hub.AssetManager")
    def test_pull_assets(self, mock_asset_manager_class):
        """Verify asset pull command correctly calls AssetManager."""
        from render_tag.cli.hub import pull_assets

        mock_manager = MagicMock()
        mock_asset_manager_class.return_value = mock_manager

        pull_assets(local_dir=self.test_dir / "assets", token="dummy_token")

        mock_asset_manager_class.assert_called_once()
        mock_manager.pull.assert_called_once_with(token="dummy_token")

    @patch("render_tag.cli.hub.AssetManager")
    def test_push_assets(self, mock_asset_manager_class):
        """Verify asset push command correctly calls AssetManager."""
        from render_tag.cli.hub import push_assets

        mock_manager = MagicMock()
        mock_asset_manager_class.return_value = mock_manager

        push_assets(local_dir=self.test_dir, token="dummy_token", commit_message="test commit")

        mock_asset_manager_class.assert_called_once()
        mock_manager.push.assert_called_once_with(token="dummy_token", commit_message="test commit")


if __name__ == "__main__":
    unittest.main()
