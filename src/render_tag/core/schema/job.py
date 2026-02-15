import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from render_tag.core.config import GenConfig
from render_tag.core.constants import CURRENT_SCHEMA_VERSION


class JobPaths(BaseModel):
    """Absolute paths for job execution."""

    model_config = ConfigDict(frozen=True)

    output_dir: Path
    logs_dir: Path
    assets_dir: Path


class JobInfrastructure(BaseModel):
    """Infrastructure settings for the job."""

    model_config = ConfigDict(frozen=True)

    max_workers: int = Field(default=1, gt=0)
    timeout_seconds: float = Field(default=3600.0, gt=0)
    worker_memory_limit_gb: float | None = None


class JobSpec(BaseModel):
    """Immutable specification for a rendering job."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(default=CURRENT_SCHEMA_VERSION, description="Schema version")
    job_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    paths: JobPaths
    infrastructure: JobInfrastructure = Field(default_factory=JobInfrastructure)

    global_seed: int
    scene_config: GenConfig

    # Metadata for reproducibility
    env_hash: str
    blender_version: str
    assets_hash: str = "unknown"  # Placeholder for now
    config_hash: str | None = None
    shard_index: int = 0

    @property
    def shard_size(self) -> int:
        return self.scene_config.dataset.num_scenes

    @classmethod
    def from_json(cls, json_str: str) -> "JobSpec":
        """Deserialize and migrate JobSpec from JSON."""
        data = json.loads(json_str)
        from render_tag.core.migration import SchemaMigrator

        migrator = SchemaMigrator()
        data = migrator.migrate(data)
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "JobSpec":
        """Load, migrate, and potentially upgrade JobSpec from a file."""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        from render_tag.core.migration import SchemaMigrator

        migrator = SchemaMigrator()
        original_version = migrator.get_version(data)
        data = migrator.migrate(data)

        if original_version != migrator.target_version:
            migrator.upgrade_file_on_disk(path, data)

        return cls.model_validate(data)


class SeedManager:
    """Manages deterministic seed generation hierarchy."""

    def __init__(self, master_seed: int):
        self.master_seed = master_seed

    def get_shard_seed(self, shard_index: int) -> int:
        """Get a deterministic seed for a specific shard index.

        Uses SHA256 hashing of (master_seed, shard_index) to produce
        a deterministic seed in O(1) time.
        """
        # Create a unique string from master seed and shard index
        seed_str = f"{self.master_seed}:{shard_index}"

        # Hash it
        hash_hex = hashlib.sha256(seed_str.encode()).hexdigest()

        # Take the first 8 characters (32 bits) and convert to int
        # This ensures we stay within standard 32-bit seed ranges
        return int(hash_hex[:8], 16)


def calculate_job_id(spec: JobSpec) -> str:
    """Calculates a deterministic SHA256 hash for the given JobSpec."""
    # Ensure stable JSON serialization
    # Exclude created_at to allow re-running same config with same ID if needed?
    # Or include it to make every run unique?
    # Usually Job ID should be unique per run.
    # But if we want content-addressable, we should exclude timestamp.
    # Let's include everything for now as a UUID-like.
    # Exclude job_id and created_at to allow deterministic generation
    spec_dict = spec.model_dump(exclude={"job_id", "created_at"}, mode="json")
    spec_json = json.dumps(spec_dict, sort_keys=True)
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

    # Try to find uv.lock in parent directories if not in CWD
    if not uv_lock_path.exists():
        curr = root_dir
        while curr.parent != curr:
            if (curr / "uv.lock").exists():
                uv_lock_path = curr / "uv.lock"
                break
            curr = curr.parent

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
