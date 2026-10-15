"""Tests for business_logic.normalize — type normalization registry (DECISION 8)."""

from __future__ import annotations

import pandas as pd

from app.business_logic import normalize


def _frame():
    return pd.DataFrame(
        {
            "subscriber_id": ["SUB_AAAA", "SUB_BBBB"],
            "cluster_id": [-1, 3],
            "arpu_monthly_tnd": ["42.5", "99.9"],
            "churn_probability": ["0.12", "0.80"],
            "activation_date": ["2024-01-15 10:00:00", "2025-06-01 08:30:00"],
            "offer_category": ["N/A", "Base Only"],
        }
    )


def test_cluster_id_normalized_to_nullable_int64():
    df = normalize.normalize_dataframe(_frame(), numeric=False, datetimes=False)
    assert str(df["cluster_id"].dtype) == "Int64"
    assert df["cluster_id"].tolist() == [-1, 3]


def test_cluster_id_keeps_sentinel_minus_one():
    df = normalize.normalize_dataframe(
        pd.DataFrame({"cluster_id": [-1, 0, 2], "x": [1, 2, 3]}),
        numeric=False,
        datetimes=False,
    )
    assert df["cluster_id"].tolist() == [-1, 0, 2]


def test_numeric_columns_converted_to_float():
    df = normalize.normalize_dataframe(_frame(), clusters=False, datetimes=False)
    assert df["arpu_monthly_tnd"].dtype == "float64"
    assert df["arpu_monthly_tnd"].tolist() == [42.5, 99.9]


def test_numeric_non_numeric_becomes_nan():
    df = pd.DataFrame({"fwa_suitability_score": [3, "junk", None], "x": [1, 2, 3]})
    out = normalize.normalize_dataframe(df, clusters=False, datetimes=False)
    assert pd.isna(out["fwa_suitability_score"].iloc[1])


def test_activation_date_converted_to_datetime():
    df = normalize.normalize_dataframe(_frame(), clusters=False, numeric=False)
    assert pd.api.types.is_datetime64_any_dtype(df["activation_date"])


def test_snapshot_to_string():
    assert normalize.snapshot_to_string(pd.Timestamp("2026-01-01")) == "2026-01-01"
    assert normalize.snapshot_to_string(None) is None
    assert pd.isna(normalize.snapshot_to_string(pd.NaT))


def test_normalize_dataframe_is_non_mutating():
    df = _frame()
    before = df.copy()
    normalize.normalize_dataframe(df)
    assert df.dtypes.equals(before.dtypes)
