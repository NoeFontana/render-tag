import csv
import json
import re

from typer.testing import CliRunner

from render_tag.cli import app

runner = CliRunner()


def clean_ansi(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def test_cli_resume_from_invalid_path():
    """Verify CLI fails when --resume-from points to a non-existent file."""
    result = runner.invoke(app, ["generate", "--resume-from", "non_existent.json"])
    assert result.exit_code != 0
    assert "Error" in result.stdout


def test_cli_resume_from_valid_job_spec(tmp_path):
    """Verify CLI correctly identifies and skips completed shards using --resume-from."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # 1. Create a dummy JobSpec
    job_spec_path = tmp_path / "job_spec.json"

    from render_tag.core.schema.job import JobPaths, JobSpec, get_env_fingerprint

    env_hash, blender_ver = get_env_fingerprint()

    from render_tag.core.config import GenConfig

    config_data = {
        "dataset": {"num_scenes": 20},
        "camera": {"resolution": [640, 480]},
        "tag": {"family": "tag36h11"},
    }
    config = GenConfig.model_validate(config_data)

    spec = JobSpec(
        job_id="resume_test",
        paths=JobPaths(
            output_dir=output_dir, logs_dir=tmp_path / "logs", assets_dir=tmp_path / "assets"
        ),
        global_seed=42,
        scene_config=config,
        env_hash=env_hash,
        blender_version=blender_ver,
    )

    with open(job_spec_path, "w") as f:
        f.write(spec.model_dump_json())

    # 2. Create Shard 0 as COMPLETE (10 scenes)
    shard_0_csv = output_dir / "tags_shard_0.csv"
    with open(shard_0_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scene_id"])
        for i in range(10):
            writer.writerow([i])
    with open(output_dir / "coco_shard_0.json", "w") as f:
        json.dump({"images": []}, f)

    # 3. Create Shard 1 as INCOMPLETE (5 scenes, expected 10)
    shard_1_csv = output_dir / "tags_shard_1.csv"
    with open(shard_1_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scene_id"])
        for i in range(5):
            writer.writerow([i])
    with open(output_dir / "coco_shard_1.json", "w") as f:
        json.dump({"images": []}, f)

    # 4. Test Case A: Shard 0 (Already Complete)
    result0 = runner.invoke(
        app,
        [
            "generate",
            "--resume-from",
            str(job_spec_path),
            "--shard-index",
            "0",
            "--batch-size",
            "10",
            "--skip-render",
        ],
    )
    stdout0 = clean_ansi(result0.stdout)
    assert "Shard 0 is already complete. Skipping." in stdout0
    assert "Resumption: Shard already complete. Skipping execution stage." in stdout0

    # 5. Test Case B: Shard 1 (Incomplete -> Aggressive Cleanup)
    # Re-create files because FinalizationStage might have cleaned them up
    # if it thought it merged them
    # (Though it shouldn't have found them if it ran for shard 0 and they were shard 1...
    # but wait, merge_shards glob matches all tags_shard_*.csv)
    shard_1_csv = output_dir / "tags_shard_1.csv"
    with open(shard_1_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["scene_id"])
        for i in range(5):
            writer.writerow([i])
    with open(output_dir / "coco_shard_1.json", "w") as f:
        json.dump({"images": []}, f)

    result1 = runner.invoke(
        app,
        [
            "generate",
            "--resume-from",
            str(job_spec_path),
            "--shard-index",
            "1",
            "--batch-size",
            "10",
            "--skip-render",
        ],
    )
    stdout1 = clean_ansi(result1.stdout)
    assert "Aggressive Cleanup: Removing invalid shard 1 files" in stdout1
    assert not shard_1_csv.exists()
