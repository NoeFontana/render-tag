import os
import sys
from pathlib import Path

# Manual path injection to find render_tag package
_src_path = str(Path(__file__).resolve().parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

try:
    from render_tag.backend import bootstrap

    bootstrap.setup_environment()
    print("Bootstrap successful")
except Exception as e:
    print(f"Bootstrap failed: {e}")

print(f"Python Version: {sys.version}")
print(f"ENV RENDER_TAG_VENV_SITE_PACKAGES: {os.environ.get('RENDER_TAG_VENV_SITE_PACKAGES')}")
print("--- sys.path (after bootstrap) ---")
for p in sys.path:
    print(p)
print("----------------")

try:
    import orjson

    print(f"orjson found: {orjson.__file__}")
except Exception as e:
    print(f"orjson error: {e}")

try:
    import pydantic

    print(f"pydantic version: {pydantic.__version__}")
except Exception as e:
    print(f"pydantic error: {e}")
