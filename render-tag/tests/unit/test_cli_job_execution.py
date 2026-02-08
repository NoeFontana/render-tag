import hashlib

from typer.testing import CliRunner

from render_tag.cli.main import app
from render_tag.schema.job import JobSpec

runner = CliRunner()

def test_cli_run_with_job_mismatch(tmp_path, monkeypatch):
    # 0. Create dummy config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("dummy: content")
    config_hash = hashlib.sha256(b"dummy: content").hexdigest()

    # 1. Create a job.json with a mismatched env_hash
    job_file = tmp_path / "job.json"
    spec = JobSpec(
        env_hash="mismatched_hash",
        blender_version="4.2.0",
        assets_hash="abc",
        config_hash=config_hash,
        seed=42,
        shard_index=0,
        shard_size=1
    )
    job_file.write_text(spec.model_dump_json())
    
    # 2. Mock uv.lock to have a different hash
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("actual content")
    
    # 3. Mock blenderproc to return correct version
    import shutil
    import subprocess
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")
    
    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())
    
    # 4. Run 'render-tag generate --job job.json'
    result = runner.invoke(app, ["generate", "--job", str(job_file)])

    assert result.exit_code != 0
    assert "Environment mismatch" in result.output

def test_cli_run_with_job_config_mismatch(tmp_path, monkeypatch):
    # 0. Create dummy config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("actual content")
    
    # 1. Create a job.json with a DIFFERENT config hash
    job_file = tmp_path / "job.json"
    spec = JobSpec(
        env_hash=hashlib.sha256(b"actual uv content").hexdigest(),
        blender_version="4.2.0",
        assets_hash="abc",
        config_hash="mismatched_config_hash",
        seed=42,
        shard_index=0,
        shard_size=1
    )
    job_file.write_text(spec.model_dump_json())
    
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("actual uv content")
    
    # Mock environment to pass
    import shutil
    import subprocess
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")
    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    result = runner.invoke(app, ["generate", "--job", str(job_file)])

    assert result.exit_code != 0
    assert "Config hash mismatch" in result.output
def test_cli_run_with_job_overrides_warning(tmp_path, monkeypatch):
    # Setup valid job and config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_file = config_dir / "default.yaml"
    config_file.write_text("dummy: content")
    config_hash = hashlib.sha256(b"dummy: content").hexdigest()

    job_file = tmp_path / "job.json"
    spec = JobSpec(
        env_hash=hashlib.sha256(b"uv").hexdigest(),
        blender_version="4.2.0",
        assets_hash="abc",
        config_hash=config_hash,
        seed=42,
        shard_index=0,
        shard_size=1
    )
    job_file.write_text(spec.model_dump_json())
    
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").write_text("uv")
    
    import shutil
    import subprocess
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/blenderproc")
    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 4.2.0\n"
            self.returncode = 0
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    # Run with conflicting CLI flags
    result = runner.invoke(app, ["generate", "--job", str(job_file), "--scenes", "5", "--seed", "100"])

    # It should still run (or at least pass the guard) and show warnings
    assert "Warning" in result.output
    assert "ignored" in result.output
    assert "Using job spec value: 1" in result.output
    assert "Using job spec value: 42" in result.output

def test_cli_run_with_job_not_found():
    result = runner.invoke(app, ["generate", "--job", "non_existent.json"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower()
