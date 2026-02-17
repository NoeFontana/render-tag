
import pytest
from unittest.mock import patch, MagicMock
from render_tag.core.resources import calculate_worker_memory_budget

def test_calculate_worker_memory_budget_explicit():
    """Verify explicit memory limit is respected."""
    # 8000 MB explicit limit, should return 8000
    assert calculate_worker_memory_budget(num_workers=4, explicit_limit_mb=8000) == 8000

def test_calculate_worker_memory_budget_auto():
    """Verify auto-tuning logic: (total * 0.75) / workers."""
    # Mock psutil to return 32GB (in bytes)
    mock_mem = MagicMock()
    mock_mem.total = 32 * 1024 * 1024 * 1024 # 32GB
    
    with patch("psutil.virtual_memory", return_value=mock_mem):
        # (32768 * 0.75) / 4 = 24576 / 4 = 6144 MB
        budget = calculate_worker_memory_budget(num_workers=4, explicit_limit_mb=None)
        assert budget == 6144

def test_calculate_worker_memory_budget_minimum():
    """Verify a sane minimum budget is returned."""
    # Mock tiny RAM: 2GB
    mock_mem = MagicMock()
    mock_mem.total = 2 * 1024 * 1024 * 1024 # 2GB
    
    with patch("psutil.virtual_memory", return_value=mock_mem):
        # (2048 * 0.75) / 8 = 1536 / 8 = 192 MB
        # We might want a floor, e.g., 512MB
        budget = calculate_worker_memory_budget(num_workers=8, explicit_limit_mb=None)
        assert budget >= 512 
