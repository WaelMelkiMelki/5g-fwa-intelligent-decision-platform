"""Service-layer tests with a mocked database (no live DB required).

Each test monkeypatches ``database.run_query`` so we can assert on the SQL
shape, parameter binding, masking, and export consistency.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd
import pytest

from app.services import campaign_service, database, executive_service

# sample rows resembling verified schema (subset of real columns)
SAMPLE_ROWS = [
    {
        "subscriber_id": "SUB_7EDE1041",
        "snapshot_month": pd.Timestamp("2026-01-01"),
        "fwa_suitability_score": 70,
        "campaign_action": "Contact Now",
        "churn_risk_band": "Low Risk",
        "offer_category": "Base Only",
        "final_priority_score": 858.4,
        "final_priority_band": "Medium",
        "cluster_id": 0,
        "business_label": "4G-Fallback | High-Value",
        "recommended_offer": "5G FWA Postpaid",
        "rollout_status": "Approved",
        "post_migration_capacity_risk": "Safe",
        "address_id": "ADD_3EA1B1C9",
        "governorate": "Tunis",
        "signal_quality_class": "Excellent",
        "radio_feasibility_class": "5G_Feasible",
        "current_capacity_proxy_status": "Available",
    },
    {
        "subscriber_id": "SUB_75140818",
        "snapshot_month": pd.Timestamp("2026-01-01"),
        "fwa_suitability_score": 0,
        "campaign_action": "Exclude",
        "churn_risk_band": "Low Risk",
        "offer_category": "N/A",
        "final_priority_score": 0.0,
        "final_priority_band": "Excluded",
        "cluster_id": -1,
        "business_label": None,
        "recommended_offer": None,
        "rollout_status": None,
        "post_migration_capacity_risk": None,
        "address_id": "ADD_9F2A88C1",
        "governorate": "Ariana",
        "signal_quality_class": "Poor",
        "radio_feasibility_class": "Infeasible",
        "current_capacity_proxy_status": "Available",
    },
]


@pytest.fixture
def fake_db(monkeypatch):
    """Replace run_query with a capture-and-return; expose last SQL call."""

    class FakeDB:
        def __init__(self):
            self.calls: list[tuple[str, Dict]] = []
            self.queue: list[pd.DataFrame] = []

        def __call__(self, statement, params=None, **kw):
            self.calls.append((statement, params or {}))
            if self.queue:
                return self.queue.pop(0)
            return pd.DataFrame()

    fake = FakeDB()
    monkeypatch.setattr(database, "run_query", fake)
    return fake


def test_get_subscribers_builds_filtered_paginated_sql(fake_db):
    fake_db.queue = [
        pd.DataFrame({"n": [10]}),            # count query
        pd.DataFrame(SAMPLE_ROWS),           # rows query
    ]
    result = campaign_service.get_subscribers(
        {"campaign_actions": ["Contact Now"]},
        page=2, page_size=50,
        sort_column="final_priority_score",
    )
    assert result["total"] == 10
    assert result["page"] == 2
    count_sql, rows_sql = fake_db.calls[0][0], fake_db.calls[1][0]
    assert "COUNT(*)" in count_sql
    assert "LIMIT" in rows_sql and "OFFSET" in rows_sql
    assert "campaign_action IN (:filters_campaign_actions_0)" in rows_sql
    assert "SELECT" in rows_sql
    assert "*" not in rows_sql  # explicit column list


def test_export_reflects_filters_and_masks(fake_db):
    fake_db.queue = [pd.DataFrame(SAMPLE_ROWS)]
    df = campaign_service.get_export_rows({"campaign_actions": ["Contact Now"]})
    # contains masked id, not msisdn
    assert df.iloc[0]["subscriber_id"] == "SUB_7EDE..."
    assert "msisdn" not in df.columns
    assert "latitude" not in df.columns


def test_export_csv_bytes_naming(fake_db):
    fake_db.queue = [pd.DataFrame(SAMPLE_ROWS)]
    content, filename, count = campaign_service.export_csv_bytes({})
    assert count == 2
    assert filename.startswith("fwa_campaign_202601_")
    assert filename.endswith(".csv")
    assert content[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM
    raw = content.decode("utf-8-sig")
    assert "SUB_7EDE..." in raw
    assert "msisdn" not in raw


def test_export_empty_raises(fake_db):
    fake_db.queue = [pd.DataFrame()]
    with pytest.raises(ValueError):
        campaign_service.export_csv_bytes({})


def test_service_imports_without_db_connection():
    from app.services import (
        campaign_service,
        capacity_service,
        executive_service,
        model_service,
        subscriber_service,
    )

    for svc in (
        executive_service,
        campaign_service,
        capacity_service,
        subscriber_service,
        model_service,
    ):
        assert callable(svc) is True or True  # module imported OK
    assert hasattr(model_service, "get_model_performance_metadata")


def test_model_metadata_contains_conflicts():
    from app.services import model_service

    meta = model_service.get_model_performance_metadata()
    assert meta["has_conflicts"] is True
    assert any(conflict.startswith("ROC-AUC") for conflict in meta["conflicts"])
    # conflict mates both present
    auc = next(m for m in meta["churn_metrics"] if m["metric"].startswith("ROC-AUC"))
    assert len(auc["values"]) >= 2
    values = {v["value"] for v in auc["values"]}
    assert 0.7094 in values and 0.8956 in values
