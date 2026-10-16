"""Tests for the leakage-controlled churn baseline."""

from __future__ import annotations

import pandas as pd
import pytest

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset
from data_pipeline.abt import build_abt
from data_pipeline.churn import ChurnConfig, ChurnModelError, train_churn_model, validate_churn_predictions


def _abt(seed: int = 51):
    return build_abt(generate_dataset(SyntheticFwaConfig(subscribers=120, cells=8, seed=seed)))


def test_churn_training_produces_valid_metrics_and_predictions():
    _, predictions, metrics = train_churn_model(_abt(), ChurnConfig(seed=3, max_iter=30))
    validate_churn_predictions(predictions)
    assert metrics["algorithm"] == "HistGradientBoostingClassifier"
    assert 0 <= metrics["roc_auc"] <= 1
    assert 0 <= metrics["average_precision"] <= 1
    assert len(predictions) == 120


def test_churn_training_is_reproducible():
    abt = _abt(52)
    config = ChurnConfig(seed=4, max_iter=30)
    first = train_churn_model(abt, config)[1].sort_values("subscriber_id").reset_index(drop=True)
    second = train_churn_model(abt, config)[1].sort_values("subscriber_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(first, second)


def test_churn_rejects_invalid_target():
    abt = _abt(53)
    abt.loc[0, "churn"] = 2
    with pytest.raises(ChurnModelError, match="only 0 and 1"):
        train_churn_model(abt, ChurnConfig(max_iter=10))


def test_churn_predictions_reject_duplicate_grain():
    abt = _abt(54)
    predictions = train_churn_model(abt, ChurnConfig(max_iter=10))[1]
    invalid = pd.concat([predictions, predictions.iloc[[0]]], ignore_index=True)
    with pytest.raises(ChurnModelError, match="unique"):
        validate_churn_predictions(invalid)
