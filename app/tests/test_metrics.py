"""Tests for pure metric computations (no database required)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.business_logic import metrics


def _df(actions=("Contact Now", "Contact Later", "Exclude", "Exclude")):
    return pd.DataFrame(
        {
            "fwa_suitability_score": [85, 0, 70, 0],
            "campaign_action": list(actions),
            "churn_risk_band": ["Low Risk", "Medium Risk", "Low Risk", "High Risk"],
            "fwa_exclusion_reason": [None, "RF_Failure", None, "Fiber_Cannibalization"],
        }
    )


def test_funnel_counts():
    df = _df()
    f = metrics.funnel_rows(df)
    assert f["total"] == 4
    assert f["eligible"] == 2
    assert f["contact_now"] == 1


def test_funnel_empty():
    f = metrics.funnel_rows(pd.DataFrame())
    assert f == {"total": 0, "eligible": 0, "contact_now": 0}


def test_action_counts():
    counts = metrics.action_counts(_df()).to_dict()
    assert counts["Exclude"] == 2
    assert counts["Contact Now"] == 1


def test_churn_band_counts():
    counts = metrics.churn_band_counts(_df()).to_dict()
    assert counts["Low Risk"] == 2
    assert counts["High Risk"] == 1


def test_exclusion_reason_none_handled():
    counts = metrics.exclusion_reason_counts(_df()).to_dict()
    assert counts["(None)"] == 2
    assert counts["RF_Failure"] == 1


def test_capacity_headroom_basic():
    cells = pd.DataFrame({"p95_prb_utilisation_pct": [79.0, 81.0, 90.0]})
    out = metrics.capacity_headroom(cells, threshold=80.0)
    assert out["cells"] == 3
    assert out["cells_at_or_over"] == 2
    assert out["max_p95"] == 90.0


def test_capacity_headroom_empty():
    out = metrics.capacity_headroom(pd.DataFrame(), threshold=80.0)
    assert out["cells"] == 0
    assert out["max_p95"] is None


def test_safe_percentage():
    assert metrics.safe_percentage(1, 4) == 25.0
    assert metrics.safe_percentage(0, 0) == 0.0


def test_pivot_table():
    df = pd.DataFrame(
        {
            "cluster_id": [0, 0, 1],
            "campaign_action": ["Exclude", "Contact Now", "Contact Now"],
        }
    )
    pivot = metrics.pivot_table(df, "cluster_id", "campaign_action")
    assert pivot.loc[0, "Exclude"] == 1
    assert pivot.loc[1, "Contact Now"] == 1
