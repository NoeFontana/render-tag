import shutil

from render_tag.core.schema.job import get_env_fingerprint


def test_get_env_fingerprint_uv_lock(tmp_path, monkeypatch):
    # Mock uv.lock path
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text("dummy content")

    def mock_which(cmd):
        if cmd == "blenderproc":
            return "/usr/bin/blenderproc"
        return None

    monkeypatch.setattr(shutil, "which", mock_which)

    # Mock subprocess.run for blenderproc --version
    import subprocess

    class MockCompletedProcess:
        def __init__(self):
            self.stdout = "BlenderProc 2.9.0\n"
            self.returncode = 0

    def mock_run(*args, **kwargs):
        return MockCompletedProcess()

    monkeypatch.setattr(subprocess, "run", mock_run)

    # We'll pass the root_dir to get_env_fingerprint for testing
    env_hash, version = get_env_fingerprint(root_dir=tmp_path)

    assert env_hash is not None
    assert len(env_hash) == 64  # SHA256
    assert version == "2.9.0"


def test_get_env_fingerprint_no_blenderproc(tmp_path, monkeypatch):
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text("dummy content")

    monkeypatch.setattr(shutil, "which", lambda x: None)

    _, version = get_env_fingerprint(root_dir=tmp_path)
    assert version == "unknown"
