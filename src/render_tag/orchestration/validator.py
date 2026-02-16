
import csv
import json
from pathlib import Path
from render_tag.core.logging import get_logger

logger = get_logger(__name__)

class ShardValidator:
    """Validates rendered shards on disk against expected specifications."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def validate_shard(self, shard_id: str | int, expected_scenes: int, delete_invalid: bool = True) -> bool:
        """Verify that a specific shard is complete on disk.
        
        Checks:
        1. ground_truth_shard_{id}.csv exists and has correct row count.
        2. coco_shard_{id}.json exists and is parseable.
        
        If delete_invalid is True, removes both files if either is invalid.
        """
        csv_path = self.output_dir / f"tags_shard_{shard_id}.csv"
        coco_path = self.output_dir / f"coco_shard_{shard_id}.json"
        
        is_valid = True
        reason = ""
        
        # 1. Check CSV
        if not csv_path.exists():
            is_valid = False
            reason = f"CSV missing: {csv_path}"
        else:
            try:
                with open(csv_path, newline="") as f:
                    # Count rows excluding header
                    reader = csv.reader(f)
                    row_count = sum(1 for _ in reader) - 1
                    if row_count != expected_scenes:
                        is_valid = False
                        reason = f"CSV row count mismatch for shard {shard_id}: expected {expected_scenes}, got {row_count}"
            except Exception as e:
                is_valid = False
                reason = f"CSV read error for shard {shard_id}: {e}"
                
        # 2. Check COCO JSON
        if is_valid:
            if not coco_path.exists():
                is_valid = False
                reason = f"COCO JSON missing: {coco_path}"
            else:
                try:
                    with open(coco_path) as f:
                        json.load(f)
                except Exception as e:
                    is_valid = False
                    reason = f"COCO JSON parse error for shard {shard_id}: {e}"
                    
        if not is_valid and reason:
            if csv_path.exists() or coco_path.exists():
                logger.warning(reason)
                if delete_invalid:
                    logger.info(f"Aggressive Cleanup: Removing invalid shard {shard_id} files")
                    if csv_path.exists(): csv_path.unlink()
                    if coco_path.exists(): coco_path.unlink()
            
        return is_valid

    def get_missing_shard_indices(self, num_shards: int, scenes_per_shard: int, total_scenes: int | None = None) -> list[int]:
        """Scan all shards and return indices of those that need (re)rendering.
        
        Automatically cleans up invalid shards.
        """
        missing_indices = []
        for i in range(num_shards):
            # Calculate expected scenes for this specific shard (last shard might be smaller)
            expected = scenes_per_shard
            if total_scenes is not None:
                start_idx = i * scenes_per_shard
                if start_idx >= total_scenes:
                    continue # Should not happen if num_shards is correct
                expected = min(scenes_per_shard, total_scenes - start_idx)
                
            if not self.validate_shard(i, expected_scenes=expected, delete_invalid=True):
                missing_indices.append(i)
                
        return missing_indices
