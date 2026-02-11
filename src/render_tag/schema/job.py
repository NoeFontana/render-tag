import hashlib
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class JobSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    env_hash: str
    blender_version: str
    assets_hash: str
    config_hash: str
    seed: int
    shard_index: int
    shard_size: int


def calculate_job_id(spec: JobSpec) -> str:
    """Calculates a deterministic SHA256 hash for the given JobSpec."""
    # Ensure stable JSON serialization
    spec_json = spec.model_dump_json(serialize_as_any=True)
    return hashlib.sha256(spec_json.encode()).hexdigest()


def get_env_fingerprint(root_dir: Path | None = None) -> tuple[str, str]:
    """
    Returns a SHA256 hash of the uv.lock file and the BlenderProc version.

    Args:
        root_dir: The project root directory. Defaults to the current working directory.

    Returns:
        A tuple of (env_hash, blender_version).
    """
    if root_dir is None:
        root_dir = Path.cwd()

    uv_lock_path = root_dir / "uv.lock"
    env_hash = "unknown"
    if uv_lock_path.exists():
        with open(uv_lock_path, "rb") as f:
            env_hash = hashlib.sha256(f.read()).hexdigest()

    blender_version = "unknown"
    if shutil.which("blenderproc"):
        try:
            result = subprocess.run(
                ["blenderproc", "--version"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                # Output format is usually "BlenderProc X.Y.Z"
                blender_version = result.stdout.strip().split()[-1]
        except Exception:
            pass

    return env_hash, blender_version
