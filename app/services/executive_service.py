"""Executive Overview service — verified KPIs, funnel, distributions.

All counts come from live queries against ``cleaned_data`` (no hard-coded
baselines; baselines are used only for the drift banner in the UI layer).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.business_logic import filtering, guards, metrics, normalize
from app.services import database

# Explicit column lists (no SELECT *).
BASE_SUBSET_COLUMNS: List[str] = [
    "s.subscriber_id",
    "s.snapshot_month",
    "s.fwa_suitability_score",
    "s.campaign_action",
    "s.churn_risk_band",
    "s.offer_category",
    "s.final_priority_score",
    "s.final_priority_band",
    "s.cluster_id",
    "s.business_label",
    "s.recommended_offer",
    "s.rollout_status",
    "s.post_migration_capacity_risk",
    "a.address_id",
    "a.governorate",
    "a.signal_quality_class",
    "a.radio_feasibility_class",
    "a.current_capacity_proxy_status",
]

BASE_JOIN_SQL = (
    "FROM cleaned_data.step15_final_campaign_list s "
    "JOIN cleaned_data.abt_subscriber_month a "
    "ON s.subscriber_id = a.subscriber_id AND s.snapshot_month = a.snapshot_month"
)

# Filter key -> DataFrame column for reference options (get_filter_options).
OPTION_SOURCE_COLUMNS: Dict[str, str] = {
    "clusters": "cluster_id",
    "churn_bands": "churn_risk_band",
    "coverage_classes": "radio_feasibility_class",
    "campaign_actions": "campaign_action",
}


def base_subscriber_subset(
    filters: Dict[str, Any],
    snapshot: Optional[str] = None,
    limit: int = 200_000,
) -> pd.DataFrame:
    """Filtered subscriber subset (SELECT explicit columns, SQL pushdown)."""
    guards.ensure_single_snapshot(database.run_query)
    predicates, params = filtering.build_predicates(filters, snapshot)
    sql = (
        "SELECT "
        + ", ".join(BASE_SUBSET_COLUMNS)
        + " "
        + BASE_JOIN_SQL
        + filtering.build_where_clause(predicates)
        + f" ORDER BY s.final_priority_score DESC NULLS LAST LIMIT {int(limit)}"
    )
    df = database.run_query(sql, params=params)
    return normalize.normalize_dataframe(df)


def get_executive_kpis(filters: Dict[str, Any], snapshot: Optional[str] = None) -> Dict[str, Any]:
    """Executive KPI pack (all counts derived from live data)."""
    df = base_subscriber_subset(filters, snapshot)
    funnel = metrics.funnel_rows(df)
    return {
        "funnel": funnel,
        "actions": metrics.action_counts(df).to_dict(),
        "churn_bands": metrics.churn_band_counts(df).to_dict(),
        "coverage_classes": (
            df["radio_feasibility_class"].fillna("(None)").value_counts().to_dict()
            if "radio_feasibility_class" in df.columns
            else {}
        ),
        "offer_categories": (
            df["offer_category"].fillna("(None)").value_counts().to_dict()
            if "offer_category" in df.columns
            else {}
        ),
    }


def get_campaign_distribution(
    filters: Dict[str, Any], snapshot: Optional[str] = None
) -> pd.DataFrame:
    """Campaign-action distribution (already-filtered counts)."""
    df = base_subscriber_subset(filters, snapshot)
    if df.empty:
        return pd.DataFrame({"campaign_action": [], "count": []})
    return (
        df["campaign_action"]
        .fillna("(None)")
        .value_counts()
        .rename("count")
        .rename_axis("campaign_action")
        .reset_index()
        .sort_values("count", ascending=False)
    )


def get_filter_options(snapshot: Optional[str] = None) -> Dict[str, List[Any]]:
    """Reference values for filter dropdowns (verified distinct values).

    Queried live so the app self-adapts to a fresh snapshot; caches are short.
    ``capacity_statuses`` exposes ONLY values present in the selected dataset
    (DECISION 4) — Constrained is not offered unless the data contains it.
    """
    options: Dict[str, List[Any]] = {
        "clusters": [],
        "churn_bands": [],
        "coverage_classes": [],
        "capacity_statuses": [],
        "offers": [],
        "campaign_actions": [],
        "snapshots": [],
        "governorates": [],
    }
    df = base_subscriber_subset({}, snapshot, limit=200_000)
    if df.empty:
        return options
    for key, column in OPTION_SOURCE_COLUMNS.items():
        options[key] = sorted(
            [v for v in df[column].dropna().unique().tolist()], key=str
        )
    options["offers"] = sorted(
        [v for v in df["offer_category"].dropna().unique().tolist()], key=str
    )
    options["capacity_statuses"] = sorted(
        [
            v
            for v in df["current_capacity_proxy_status"]
            .dropna()
            .unique()
            .tolist()
        ],
        key=str,
    )
    months = sorted(df["snapshot_month"].dropna().unique().tolist())
    options["snapshots"] = [str(m) for m in months]
    if "governorate" in df.columns:
        options["governorates"] = sorted(
            [v for v in df["governorate"].dropna().unique().tolist()], key=str
        )
    return options
