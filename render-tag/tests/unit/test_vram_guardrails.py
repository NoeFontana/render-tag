import sys
from pathlib import Path

from render_tag.orchestration.worker_pool import WorkerPool


def test_vram_guardrail_restart(tmp_path):
    project_root = Path(__file__).resolve().parents[3]
    src_path = project_root / "render-tag" / "src"
    
    # Create a backend that reports HIGH VRAM
    dummy_script = tmp_path / "high_vram_backend.py"
    dummy_script.write_text(f"""
import sys
import argparse
from pathlib import Path
sys.path.append(r'{src_path}')
from render_tag.backend.zmq_server import ZmqBackendServer
from render_tag.schema.hot_loop import Telemetry

class HighVramServer(ZmqBackendServer):
    def get_telemetry(self) -> Telemetry:
        tel = super().get_telemetry()
        tel.vram_used_mb = 5000.0 # Force high VRAM
        return tel

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    server = HighVramServer(port=args.port)
    server.run()
""")

    # Pool with 1000MB threshold
    with WorkerPool(
        num_workers=1,
        base_port=7100,
        blender_script=dummy_script,
        blender_executable=sys.executable,
        use_blenderproc=False,
        vram_threshold_mb=1000.0
    ) as pool:
        worker = pool.get_worker()
        original_pid = worker.process.pid
        
        # Releasing should trigger restart due to 5000MB > 1000MB
        pool.release_worker(worker)
        
        reborn = pool.get_worker()
        assert reborn.process.pid != original_pid
        assert reborn.is_healthy()
