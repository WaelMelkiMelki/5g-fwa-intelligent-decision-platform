"""Tests for the local subscriber-month ABT transformation."""

from __future__ import annotations

import pandas as pd
import pytest

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset
from data_pipeline.abt import build_abt, save_abt, validate_abt


def test_build_abt_preserves_subscriber_month_grain():
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=30, cells=4, seed=5))
    abt = build_abt(dataset)
    validate_abt(abt)
    assert len(abt) == 30
    assert abt[["subscriber_id", "snapshot_month"]].duplicated().sum() == 0
    assert {"arpu_band", "tenure_band", "multi_line_flag", "streaming_heavy_flag"}.issubset(abt.columns)
    assert "governorate_coverage" not in abt.columns
    assert len(abt.columns) == 45


def test_abt_joins_cell_kpis_and_derives_capacity_status():
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=20, cells=3, seed=8))
    abt = build_abt(dataset)
    expected = dataset["cell_kpis"].set_index("cell_id").loc[
        abt["dominant_serving_cell_id"], "p95_prb_utilisation_pct"
    ].to_numpy()
    assert (abt["p95_prb_utilisation_pct"].to_numpy() == expected).all()
    assert set(abt["current_capacity_proxy_status"]) <= {"Available", "Constrained"}


def test_abt_save_writes_manifest_and_round_trips(tmp_path):
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=10, cells=2, seed=12)))
    manifest = save_abt(abt, tmp_path)
    saved = pd.read_parquet(tmp_path / "abt_subscriber_month.parquet")
    assert manifest["rows"] == 10
    pd.testing.assert_frame_equal(saved, abt)
    assert (tmp_path / "abt_manifest.json").exists()


def test_validate_abt_rejects_duplicate_grain():
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=8, cells=2, seed=14)))
    invalid = pd.concat([abt, abt.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="grain must be unique"):
        validate_abt(invalid)
