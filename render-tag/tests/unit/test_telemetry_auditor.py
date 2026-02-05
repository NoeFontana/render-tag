from render_tag.schema.hot_loop import Telemetry
from render_tag.tools.telemetry_auditor import TelemetryAuditor


def test_telemetry_auditor_collection():
    auditor = TelemetryAuditor()
    
    tel1 = Telemetry(vram_used_mb=100, vram_total_mb=8000, cpu_usage_percent=10, state_hash="h1", uptime_seconds=10)
    tel2 = Telemetry(vram_used_mb=200, vram_total_mb=8000, cpu_usage_percent=20, state_hash="h1", uptime_seconds=20)
    
    auditor.add_entry("w1", tel1)
    auditor.add_entry("w1", tel2)
    
    df = auditor.get_dataframe()
    assert len(df) == 2
    assert df["vram_used_mb"].sum() == 300
    assert df["worker_id"][0] == "w1"

def test_telemetry_analysis():
    auditor = TelemetryAuditor()
    tel = Telemetry(vram_used_mb=500, vram_total_mb=8000, cpu_usage_percent=50, state_hash="h1", uptime_seconds=100)
    auditor.add_entry("w1", tel)
    
    stats = auditor.analyze_throughput()
    assert stats["max_vram_mb"] == 500
    assert stats["event_count"] == 1

def test_telemetry_save(tmp_path):
    auditor = TelemetryAuditor()
    tel = Telemetry(vram_used_mb=500, vram_total_mb=8000, cpu_usage_percent=50, state_hash="h1", uptime_seconds=100)
    auditor.add_entry("w1", tel)
    
    csv_path = tmp_path / "telemetry.csv"
    auditor.save_csv(csv_path)
    assert csv_path.exists()
