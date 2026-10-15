"""Tests for source-table and ABT quality reporting."""

from __future__ import annotations

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset
from data_pipeline.abt import build_abt
from data_pipeline.quality import run_quality_checks, save_quality_report


def test_quality_report_passes_for_clean_dataset(tmp_path):
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=25, cells=4, seed=21))
    report = run_quality_checks(dataset, build_abt(dataset))
    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["failed"] == 0
    save_quality_report(report, tmp_path / "quality.json")
    assert (tmp_path / "quality.json").exists()


def test_quality_report_detects_unknown_usage_cell():
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=25, cells=4, seed=22))
    dataset["usage_monthly"].loc[0, "dominant_serving_cell_id"] = "CELL_UNKNOWN"
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=25, cells=4, seed=22)))
    report = run_quality_checks(dataset, abt)
    assert report["summary"]["status"] == "FAIL"
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "usage_cells_exist" in failed_names
