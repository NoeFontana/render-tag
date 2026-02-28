import csv
import json

from render_tag.orchestration.validator import ShardValidator


def test_shard_validator_valid_shard(tmp_path):
    """Test validator with a perfectly complete shard."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    shard_id = "shard_0"
    csv_path = output_dir / f"tags_shard_{shard_id}.csv"
    coco_path = output_dir / f"coco_shard_{shard_id}.json"

    # Create CSV with 10 rows + header
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scene_id", "tag_id"])
        for i in range(10):
            writer.writerow([i, 1])

    # Create valid JSON
    with open(coco_path, "w") as f:
        json.dump({"images": []}, f)

    validator = ShardValidator(output_dir)
    assert validator.validate_shard(shard_id, expected_scenes=10)
    assert csv_path.exists()
    assert coco_path.exists()


def test_shard_validator_missing_files(tmp_path):
    """Test validator when files are missing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    validator = ShardValidator(output_dir)
    assert not validator.validate_shard("missing", expected_scenes=10)


def test_shard_validator_incomplete_csv(tmp_path):
    """Test validator when CSV has fewer rows than expected."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    shard_id = "incomplete"
    csv_path = output_dir / f"tags_shard_{shard_id}.csv"
    coco_path = output_dir / f"coco_shard_{shard_id}.json"

    # Create CSV with only 5 rows + header (expected 10)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scene_id", "tag_id"])
        for i in range(5):
            writer.writerow([i, 1])

    with open(coco_path, "w") as f:
        json.dump({}, f)

    validator = ShardValidator(output_dir)
    # validate_shard should return False AND delete the files if delete_invalid=True
    assert not validator.validate_shard(shard_id, expected_scenes=10, delete_invalid=True)
    assert not csv_path.exists()
    assert not coco_path.exists()


def test_shard_validator_get_missing_shards(tmp_path):
    """Test high-level method to scan multiple shards."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Shard 0: Valid
    csv0 = output_dir / "tags_shard_0.csv"
    with open(csv0, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["h"])
        for i in range(5):
            writer.writerow([i])
    with open(output_dir / "coco_shard_0.json", "w") as f:
        json.dump({}, f)

    # Shard 1: Incomplete (3 rows)
    csv1 = output_dir / "tags_shard_1.csv"
    with open(csv1, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["h"])
        for i in range(3):
            writer.writerow([i])
    with open(output_dir / "coco_shard_1.json", "w") as f:
        json.dump({}, f)

    # Shard 2: Missing entirely

    validator = ShardValidator(output_dir)
    missing = validator.get_missing_shard_indices(num_shards=3, scenes_per_shard=5)

    assert 1 in missing
    assert 2 in missing
    assert 0 not in missing

    # Verify shard 1 was cleaned up
    assert not csv1.exists()
