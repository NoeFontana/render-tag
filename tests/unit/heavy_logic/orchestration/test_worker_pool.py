from unittest.mock import MagicMock, patch

from render_tag.orchestration import UnifiedWorkerOrchestrator


def test_worker_pool_lifecycle(tmp_path):
    """
    Staff Engineer: Test pool lifecycle using mocks to avoid OOM and subprocess overhead.
    """
    with patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess") as mock_worker_cls:
        # Configure mock worker
        def create_mock_worker(worker_id, *args, **kwargs):
            m = MagicMock()
            m.worker_id = worker_id
            m.is_healthy.return_value = True
            m.max_renders = None
            m.renders_completed = 0
            return m
        
        mock_worker_cls.side_effect = create_mock_worker

        with UnifiedWorkerOrchestrator(
            num_workers=2,
            use_blenderproc=False,
            mock=True,
        ) as pool:
            assert len(pool.workers) == 2
            assert mock_worker_cls.call_count == 2

            # Test queue access
            w1 = pool.get_worker()
            w2 = pool.get_worker()
            assert w1.worker_id != w2.worker_id

            pool.release_worker(w1)
            pool.release_worker(w2)


def test_worker_pool_resilience(tmp_path):
    """Verify that the pool restarts unhealthy workers."""
    with patch("render_tag.orchestration.orchestrator.PersistentWorkerProcess") as mock_worker_cls:
        m1 = MagicMock()
        m1.worker_id = "worker-0"
        m1.is_healthy.return_value = False # Force restart
        m1.renders_completed = 0
        m1.max_renders = 10
        m1.client = None # Skip telemetry check
        
        m2 = MagicMock()
        m2.worker_id = "worker-0"
        m2.is_healthy.return_value = True
        
        mock_worker_cls.side_effect = [m1, m2]

        with UnifiedWorkerOrchestrator(
            num_workers=1,
            use_blenderproc=False,
            mock=True,
        ) as pool:
            worker = pool.get_worker()
            assert worker is m1
            
            # Releasing should trigger restart because m1 is unhealthy
            pool.release_worker(worker)
            
            # Should have called constructor again for restart
            assert mock_worker_cls.call_count == 2
            
            worker_reborn = pool.get_worker()
            assert worker_reborn is m2


def test_worker_throttling_env(tmp_path):
    """Verify that thread budgets are correctly calculated."""
    from unittest.mock import patch

    with patch("os.cpu_count", return_value=16), UnifiedWorkerOrchestrator(
        num_workers=2,
        use_blenderproc=False,
        mock=True,
    ) as pool:
        # (16 - 2) / 2 = 7
        assert pool.thread_budget == 7
