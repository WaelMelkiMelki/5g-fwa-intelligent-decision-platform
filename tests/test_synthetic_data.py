"""Focused tests for the reproducible synthetic FWA source environment."""

from __future__ import annotations

import pandas as pd
import pytest

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset, validate_dataset


def test_generation_is_reproducible():
    first = generate_dataset(SyntheticFwaConfig(subscribers=25, cells=4, seed=7))
    second = generate_dataset(SyntheticFwaConfig(subscribers=25, cells=4, seed=7))
    for table_name in first:
        pd.testing.assert_frame_equal(first[table_name], second[table_name])


def test_tables_have_expected_grains_and_relationships():
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=40, cells=5, seed=11))
    validate_dataset(dataset)
    assert len(dataset["crm_subscribers"]) == 40
    assert len(dataset["cell_kpis"]) == 5
    assert set(dataset["usage_monthly"]["subscriber_id"]) == set(dataset["crm_subscribers"]["subscriber_id"])
    assert set(dataset["coverage_addresses"]["serving_cell_id"]).issubset(set(dataset["cell_kpis"]["cell_id"]))


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError, match="must be positive"):
        generate_dataset(SyntheticFwaConfig(subscribers=0))


def test_quality_anomalies_are_detected():
    dataset = generate_dataset(SyntheticFwaConfig(subscribers=20, cells=3, seed=3, inject_anomalies=True))
    with pytest.raises(ValueError, match="Usage grain"):
        validate_dataset(dataset)
