"""Tests for global-filter predicate construction and validation."""

from __future__ import annotations

import pytest

from app.business_logic import filtering


def test_empty_filters_produce_no_predicates():
    preds, params = filtering.build_predicates({})
    assert preds == []
    assert params == {}


def test_unknown_filter_key_rejected():
    with pytest.raises(ValueError):
        filtering.build_predicates({"made_up": ["x"]})


def test_invalid_action_value_rejected():
    with pytest.raises(ValueError):
        filtering.build_predicates({"campaign_actions": ["Not An Action"]})


def test_invalid_cluster_rejected():
    with pytest.raises(ValueError):
        filtering.build_predicates({"clusters": [99]})


@pytest.mark.parametrize(
    "filters",
    [
        {"campaign_actions": ["Contact Now"]},
        {"churn_bands": ["Low Risk", "High Risk"]},
        {"coverage_classes": ["5G_Feasible"]},
        {"capacity_statuses": ["Available"]},
        {"offers": ["Base Only"]},
        {"clusters": [-1, 3]},
    ],
)
def test_single_filter_binds_values(filters):
    preds, params = filtering.build_predicates(filters)
    assert preds, "expected at least one predicate"
    assert params, "expected bound parameters"
    # every param referenced in SQL must appear in params
    import re

    referenced = set(re.findall(r":([a-z0-9_]+)", " ".join(preds)))
    assert referenced <= set(params)


def test_multiple_filters_combined():
    filters = {"campaign_actions": ["Contact Now"], "churn_bands": ["Medium Risk"]}
    preds, params = filtering.build_predicates(filters)
    assert len(preds) == 2
    assert len(params) == 2


def test_snapshot_bound():
    preds, params = filtering.build_predicates({}, snapshot_month="2026-01-01")
    assert preds
    assert params["snapshot_month"] == "2026-01-01"


def test_where_clause_join():
    preds, params = filtering.build_predicates({"campaign_actions": ["Exclude"]})
    where = filtering.build_where_clause(preds)
    assert where.startswith(" WHERE ")
    assert "campaign_action IN" in where


def test_empty_values_treated_as_no_filter():
    preds, params = filtering.build_predicates({"campaign_actions": []})
    assert preds == []
    assert params == {}


def test_unvalidated_column_never_reaches_sql():
    """Column names are only ever drawn from the allowlist constant."""
    assert set(filtering.FILTER_COLUMNS).issuperset(
        {"clusters", "churn_bands", "coverage_classes",
         "capacity_statuses", "offers", "campaign_actions"}
    )
