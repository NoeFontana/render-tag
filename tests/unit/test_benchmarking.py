"""
Unit tests for benchmarking utilities.
"""

from render_tag.tools.benchmarking import Benchmarker


def test_benchmarker_measure() -> None:
    bench = Benchmarker("test")
    with bench.measure("stage1"):
        pass

    report = bench.get_report()
    assert "stage1" in report.stages
    assert report.stages["stage1"].duration_sec >= 0


def test_performance_report_log(caplog) -> None:
    import logging

    bench = Benchmarker("test")
    bench.report.add_stage("load", 1.5)
    bench.report.add_stage("render", 3.5)

    with caplog.at_level(logging.INFO):
        bench.report.log_summary()

    assert "Performance Summary: test" in caplog.text
    assert "load" in caplog.text
    assert "render" in caplog.text
    assert "1.500s" in caplog.text
    assert "3.500s" in caplog.text
    assert "30.0%" in caplog.text  # 1.5 / 5.0 * 100
    assert "70.0%" in caplog.text  # 3.5 / 5.0 * 100
