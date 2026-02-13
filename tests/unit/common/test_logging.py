import json
import logging
from pathlib import Path

import numpy as np

from render_tag.common.logging import JSONFormatter


def test_json_formatter_basic():
    formatter = JSONFormatter()
    # logger = logging.getLogger("test_basic") # Unused
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="test message",
        args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "test message"
    assert data["type"] == "log"
    assert "timestamp" in data

def test_json_formatter_complex_types():
    formatter = JSONFormatter()
    
    # Mock a mathutils-like object
    class Vector:
        def __init__(self, values):
            self.values = values
        def to_list(self):
            return self.values
    
    # or a Matrix-like that is iterable
    class Matrix:
        def __init__(self, values):
            self.values = values
        def __iter__(self):
            return iter(self.values)

    payload = {
        "path": Path("/tmp/test"),
        "array": np.array([1, 2, 3]),
        "vec": Vector([1.0, 2.0, 3.0]),
        "mat": Matrix([[1, 0], [0, 1]])
    }
    
    record = logging.LogRecord(
        name="test_complex",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="complex message",
        args=(),
        exc_info=None
    )
    record.payload = payload
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["payload"]["path"] == "/tmp/test"
    assert data["payload"]["array"] == [1, 2, 3]
    assert data["payload"]["vec"] == [1.0, 2.0, 3.0]
    assert data["payload"]["mat"] == [[1, 0], [0, 1]]

def test_json_formatter_error_type():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_error",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="error message",
        args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["type"] == "error"

def test_json_formatter_custom_type():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_progress",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="progress update",
        args=(),
        exc_info=None
    )
    record.log_type = "progress"
    record.payload = {"progress": 0.5}
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["type"] == "progress"
    assert data["payload"]["progress"] == 0.5
