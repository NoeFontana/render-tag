import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ChecksumManifest:
    """
    Manages the checksums.json for a generated dataset.
    Links output files to their originating Job ID via SHA256 hashes.
    """

    def __init__(self, job_id: str, output_dir: Path):
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.files: dict[str, str] = {}

    def add_file(self, file_path: Path):
        """Calculates hash for a file and adds it to the manifest."""
        abs_path = Path(file_path).absolute()
        if not abs_path.exists():
            logger.warning(f"File not found for manifest: {abs_path}")
            return

        rel_path = abs_path.relative_to(self.output_dir.absolute())

        hasher = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

        self.files[str(rel_path)] = hasher.hexdigest()

    def add_directory(self, dir_path: Path, pattern: str = "*"):
        """Recursively adds all files matching a pattern in a directory."""
        dir_path = Path(dir_path)
        if not dir_path.exists():
            return

        for p in dir_path.rglob(pattern):
            if p.is_file():
                self.add_file(p)

    def save(self, filename: str = "checksums.json") -> Path:
        """Saves the checksums to the output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename

        data = {"job_id": self.job_id, "files": self.files}

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return output_path
