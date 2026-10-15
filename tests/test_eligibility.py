"""Tests for the explainable FWA eligibility decision engine."""

from __future__ import annotations

import pandas as pd
import pytest

from data_generation.synthetic_fwa import SyntheticFwaConfig, generate_dataset
from data_pipeline.abt import build_abt
from data_pipeline.eligibility import score_eligibility, validate_eligibility


def _scores(seed: int = 31) -> pd.DataFrame:
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=40, cells=5, seed=seed)))
    scores = score_eligibility(abt)
    validate_eligibility(scores)
    return scores


def test_scores_preserve_abt_grain_and_bounds():
    scores = _scores()
    assert len(scores) == 40
    assert scores["fwa_suitability_score"].between(0, 100).all()
    assert scores[["subscriber_id", "snapshot_month"]].duplicated().sum() == 0


def test_hard_stop_precedence_and_reasons():
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=12, cells=3, seed=32)))
    abt.loc[0, ["fiber_coverage_flag", "radio_feasibility_class"]] = [True, "Infeasible"]
    abt.loc[1, "radio_feasibility_class"] = "Infeasible"
    abt.loc[2, "current_capacity_proxy_status"] = "Constrained"
    scores = score_eligibility(abt)
    assert scores.loc[0, "fwa_exclusion_reason"] == "Fiber_Cannibalization"
    assert scores.loc[1, "fwa_exclusion_reason"] == "RF_Failure"
    assert scores.loc[2, "fwa_exclusion_reason"] == "Cell_Overload"
    assert (scores.loc[[0, 1, 2], "fwa_suitability_score"] == 0).all()


def test_low_arpu_and_no_5g_penalties_are_explainable():
    abt = build_abt(generate_dataset(SyntheticFwaConfig(subscribers=6, cells=2, seed=33)))
    abt.loc[0, ["fiber_coverage_flag", "radio_feasibility_class", "coverage_5g_flag", "arpu_band"]] = [False, "4G_Fallback", False, "LV"]
    scores = score_eligibility(abt)
    assert scores.loc[0, "fwa_suitability_score"] == 65
    assert pd.isna(scores.loc[0, "fwa_exclusion_reason"])


def test_invalid_score_output_is_rejected():
    scores = _scores()
    scores.loc[0, "fwa_suitability_score"] = 0
    with pytest.raises(ValueError, match="exclusion reason"):
        validate_eligibility(scores)
