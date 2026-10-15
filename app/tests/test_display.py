"""Tests for business_logic.display — sentinel label aliases (DECISION 2)."""

from __future__ import annotations

import pandas as pd

from app.business_logic import display as D


def test_cluster_minus_one_label():
    assert D.display_value("cluster_id", -1) == "Not Segmented"
    assert D.display_value("cluster_id", 2) == 2


def test_offer_na_label():
    assert D.display_value("offer_category", "N/A") == "No Offer"
    assert D.display_value("offer_category", "Base Only") == "Base Only"


def test_null_rollout_label():
    assert D.display_value("rollout_status", None) == "Not Applicable"
    assert D.display_value("rollout_status", "Approved") == "Approved"


def test_null_post_migration_label():
    assert D.display_value("post_migration_capacity_risk", None) == "Not Applicable"


def test_apply_sentinel_labels_on_dataframe():
    df = pd.DataFrame(
        {
            "subscriber_id": ["SUB_A", "SUB_B", "SUB_C"],
            "cluster_id": [-1, 1, 0],
            "offer_category": ["N/A", "Base Only", "Base + IPTV"],
            "rollout_status": [None, "Approved", None],
            "post_migration_capacity_risk": [None, "Safe", None],
        }
    )
    out = D.apply_sentinel_labels(df)
    assert out["cluster_id"].tolist() == ["Not Segmented", 1, 0]
    assert out["offer_category"].tolist() == ["No Offer", "Base Only", "Base + IPTV"]
    assert out["rollout_status"].tolist() == [
        "Not Applicable",
        "Approved",
        "Not Applicable",
    ]
    assert out["post_migration_capacity_risk"].tolist() == [
        "Not Applicable",
        "Safe",
        "Not Applicable",
    ]
    # original DataFrame must remain unchanged (display-only mapping)
    assert df["offer_category"].tolist() == ["N/A", "Base Only", "Base + IPTV"]
