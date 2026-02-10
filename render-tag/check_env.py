import os
import sys

print(f"Executable: {sys.executable}")
print(f"Path: {sys.path}")
print(f"CWD: {os.getcwd()}")
try:
    import pytest

    print(f"pytest version: {pytest.__version__}")
except ImportError:
    print("pytest not found")
