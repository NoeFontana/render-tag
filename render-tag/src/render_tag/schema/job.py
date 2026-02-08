import hashlib
import json
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
