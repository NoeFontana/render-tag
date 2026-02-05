import subprocess


def get_git_hash() -> str:
    """Get the current git commit hash.
    
    Returns:
        Short git hash or 'unknown' if git command fails.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode("ascii").strip()
    except Exception:
        return "unknown"
