import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from render_tag.data_io.writers import AtomicWriter, COCOWriter


class TestAtomicWriter(AtomicWriter):
    """Concrete implementation for testing mixin."""
    pass

def test_atomic_write_success(tmp_path):
    """Verify happy path: write -> flush -> fsync -> rename."""
    writer = TestAtomicWriter()
    target_path = tmp_path / "test.json"
    data = {"key": "value"}
    
    with patch("os.fsync") as mock_fsync:
        writer._write_atomic(target_path, data)
        
        # Verify file exists and content is correct
        assert target_path.exists()
        with open(target_path) as f:
            loaded = json.load(f)
        assert loaded == data
        
        # Verify fsync called
        assert mock_fsync.called

def test_atomic_write_sequence():
    """Verify exact sequence of operations using mocks."""
    writer = TestAtomicWriter()
    target_path = Path("/fake/target.json")
    temp_path = Path("/fake/target.tmp")
    data = {"foo": "bar"}
    
    with patch("builtins.open", mock_open()) as mock_file, \
         patch("os.fsync") as mock_fsync, \
         patch.object(Path, "rename") as mock_rename, \
         patch.object(Path, "with_suffix", return_value=temp_path):
             
        writer._write_atomic(target_path, data)
        
        handle = mock_file()
        
        # Verify flush called before fsync
        handle.flush.assert_called()
        
        # Verify fsync called with file descriptor
        mock_fsync.assert_called_with(handle.fileno())
        
        # Verify rename called last
        mock_rename.assert_called_with(target_path)

def test_atomic_write_failure_cleanup(tmp_path):
    """Verify temp file is cleaned up on error."""
    writer = TestAtomicWriter()
    target_path = tmp_path / "fail.json"
    temp_path = target_path.with_suffix(".tmp")
    data = {"a": 1}
    
    # Simulate error during JSON dump
    with patch("json.dump", side_effect=RuntimeError("Disk full")), pytest.raises(RuntimeError):
        writer._write_atomic(target_path, data)
            
    # Verify temp file is gone
    assert not temp_path.exists()
    # Target should not exist either
    assert not target_path.exists()

def test_coco_writer_atomic(tmp_path):
    """Verify COCOWriter uses atomic pattern."""
    output_dir = tmp_path / "coco"
    writer = COCOWriter(output_dir)
    writer.add_image("test.png", 100, 100)
    
    # Spy on _write_atomic
    with patch.object(AtomicWriter, "_write_atomic", wraps=writer._write_atomic) as mock_atomic:
        out_path = writer.save()
        
        assert out_path.exists()
        mock_atomic.assert_called_once()
