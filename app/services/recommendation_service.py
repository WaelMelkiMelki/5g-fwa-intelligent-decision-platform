"""Offer Recommendations service — step13 content (joined, paginated, masked
at the display layer).

All rows come from ``cleaned_data.step13_recommendations`` joined to the
final-campaign list so page filters (population, cluster, churn, action,
offer) apply with SQL pushdown. ``offer_category = 'N/A'`` is the stored
sentinel for "no offer"; the display layer maps it via
``display.apply_sentinel_labels``. Reason codes are shown only when present:
"Recommendation explanation unavailable in the current dataset." otherwise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.business_logic import filtering, guards
from app.services import database

RECOMMENDATION_COLUMNS: List[str] = [
    "r.subscriber_id",
    "s.fwa_suitability_score",
    "r.tier1_base_plan",
    "r.tier2_addons",
    "r.recommended_offer",
    "r.offer_category",
    "r.reason_codes",
    "s.campaign_action",
    "s.churn_risk_band",
    "s.final_priority_score",
    "s.cluster_id",
    "s.business_label",
]

RECOMMENDATION_JOIN_SQL = (
    "FROM cleaned_data.step15_final_campaign_list s "
    "JOIN cleaned_data.step13_recommendations r "
    "ON r.subscriber_id = s.subscriber_id"
)


def get_offer_distribution(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Offer-category distribution (N/A -> 'No Offer' display alias)."""
    df = get_recommendation_page(filters, snapshot, page_size=200_000)["rows"]
    if df.empty:
        return pd.DataFrame({"offer_category": [], "count": []})
    col = df["offer_category"].replace("N/A", "No Offer").fillna("(None)")
    return (
        col.value_counts()
        .rename("count")
        .rename_axis("offer_category")
        .reset_index()
        .sort_values("count", ascending=False)
    )


def get_tier1_distribution(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Tier-1 base-plan distribution (eligible rows only)."""
    guards.ensure_single_snapshot(database.run_query)
    predicates, params = filtering.build_predicates(filters, snapshot)
    predicates.append("s.fwa_suitability_score > 0")
    sql = (
        "SELECT r.tier1_base_plan AS plan_name, COUNT(*) AS count "
        + RECOMMENDATION_JOIN_SQL
        + filtering.build_where_clause(predicates)
        + " GROUP BY r.tier1_base_plan ORDER BY count DESC"
    )
    df = database.run_query(sql, params=params)
    return df


def get_addon_distribution(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Tier-2 add-on split (comma-separated component counts)."""
    guards.ensure_single_snapshot(database.run_query)
    predicates, params = filtering.build_predicates(filters, snapshot)
    predicates.append("s.fwa_suitability_score > 0")
    sql = (
        "SELECT r.tier2_addons AS addons, COUNT(*) AS count "
        + RECOMMENDATION_JOIN_SQL
        + filtering.build_where_clause(predicates)
        + " GROUP BY r.tier2_addons ORDER BY count DESC"
    )
    df = database.run_query(sql, params=params)
    return df


def get_recommendation_page(
    filters: Dict[str, Any],
    snapshot: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """Paginated recommendation rows (real ids; page masks its display copy)."""
    guards.ensure_single_snapshot(database.run_query)
    predicates, params = filtering.build_predicates(filters, snapshot)
    where = filtering.build_where_clause(predicates)
    count_sql = "SELECT COUNT(*) AS n " + RECOMMENDATION_JOIN_SQL + where
    rows_sql = (
        "SELECT " + ", ".join(RECOMMENDATION_COLUMNS) + " " + RECOMMENDATION_JOIN_SQL
        + where
        + " ORDER BY s.final_priority_score DESC NULLS LAST"
        + f" LIMIT {int(page_size)} OFFSET {int((page - 1) * page_size)}"
    )
    n = int(database.run_query(count_sql, params=params).iloc[0]["n"])
    rows = database.run_query(rows_sql, params=params)
    return {"rows": rows, "total": n, "page": page, "page_size": page_size}


def get_recommendation_overview(filters: Dict[str, Any], snapshot: Optional[str] = None) -> Dict[str, Any]:
    """Overall recommendation stats (all computed live)."""
    df = get_recommendation_page(filters, snapshot, page_size=200_000)["rows"]
    total = int(len(df))
    no_offer = int((df["offer_category"] == "N/A").sum()) if total else 0
    has_offer = total - no_offer
    reasons = 0
    if total:
        clean = df["reason_codes"].fillna("").astype(str).str.strip().str.lower()
        reasons = int(
            ((clean != "") & (clean != "[]") & (clean != "none") & (clean != "<na>")).sum()
        )
    return {
        "total": total,
        "with_offer": has_offer,
        "no_offer": no_offer,
        "with_reason": reasons,
        "without_reason": total - reasons,
    }
