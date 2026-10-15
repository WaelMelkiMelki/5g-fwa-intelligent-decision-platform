"""Coverage & Eligibility service — coverage intelligence and eligibility.

Aggregate-only: no subscriber identifiers are ever selected; geo output is
cell-centroid aggregates (AVG(latitude)/AVG(longitude) per serving cell) —
never subscriber-level coordinates. The subscriber->address-grid join is
verified (12,412/12,412 rows) in the data-quality page and by
``verify_schema_mapping.sql``; the map layer therefore shows a privacy-safe
cell centroid overlay.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from app.business_logic import filtering, normalize
from app.services import database, executive_service

BASE_SUBSET_SQL = (
    "FROM cleaned_data.step15_final_campaign_list s "
    "JOIN cleaned_data.abt_subscriber_month a "
    "ON a.subscriber_id = s.subscriber_id AND a.snapshot_month = s.snapshot_month"
)


def _subset(filters: Dict[str, Any], snapshot: Optional[str]) -> pd.DataFrame:
    """Filtered step15 ⋈ abt subscriber subset (reuses executive subset)."""
    return executive_service.base_subscriber_subset(filters, snapshot)


def get_coverage_kpis(filters: Dict[str, Any], snapshot: Optional[str] = None) -> Dict[str, Any]:
    """Coverage & eligibility KPIs — all values computed live."""
    df = _subset(filters, snapshot)
    total = int(len(df))
    eligible = int((df["fwa_suitability_score"] > 0).sum()) if total else 0
    return {
        "total": total,
        "eligible": eligible,
        "excluded": total - eligible,
        "coverage_classes": (
            df["radio_feasibility_class"].fillna("(None)").value_counts().to_dict()
            if "radio_feasibility_class" in df.columns
            else {}
        ),
        "signal_quality": (
            df["signal_quality_class"].fillna("(None)").value_counts().to_dict()
            if "signal_quality_class" in df.columns
            else {}
        ),
    }


def get_suitability_distribution(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Suitability-band distribution (verified bands; 'Excluded' labelled)."""
    predicates, params = filtering.build_predicates(filters, snapshot)
    sql = (
        "SELECT s.fwa_suitability_band AS band, COUNT(*) AS count "
        + BASE_SUBSET_SQL
        + filtering.build_where_clause(predicates)
        + " GROUP BY s.fwa_suitability_band ORDER BY count DESC"
    )
    df = database.run_query(sql, params=params)
    df = normalize.normalize_dataframe(df)
    if df.empty:
        return pd.DataFrame({"band": [], "count": []})
    df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)
    df["band"] = df["band"].fillna("(None)")
    return df


def get_exclusion_reasons(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Exclusion-reason distribution (abt.fwa_exclusion_reason, SQL pushdown)."""
    predicates, params = filtering.build_predicates(filters, snapshot)
    sql = (
        "SELECT a.fwa_exclusion_reason AS reason, COUNT(*) AS count "
        + BASE_SUBSET_SQL
        + filtering.build_where_clause(predicates)
        + " GROUP BY a.fwa_exclusion_reason ORDER BY count DESC"
    )
    df = database.run_query(sql, params=params)
    df = normalize.normalize_dataframe(df)
    if df.empty:
        return pd.DataFrame({"reason": [], "count": []})
    df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)
    df["reason"] = df["reason"].fillna("(None)")
    return df


def get_cell_risk_table(filters: Dict[str, Any], snapshot: Optional[str] = None) -> pd.DataFrame:
    """Per-cell aggregate (subscriber density + capacity KPIs)."""
    predicates, params = filtering.build_predicates(filters, snapshot)
    if not predicates:
        where = ""
    else:
        where = " WHERE " + " AND ".join(predicates)
    sql = (
        "SELECT a.dominant_serving_cell_id AS cell_id, "
        "       COUNT(*) AS subscribers, "
        "       ROUND(AVG(a.p95_prb_utilisation_pct)::numeric, 1) AS avg_p95, "
        "       ROUND(MAX(a.p95_prb_utilisation_pct)::numeric, 1) AS max_p95 "
        + BASE_SUBSET_SQL
        + where
        + " GROUP BY a.dominant_serving_cell_id ORDER BY subscribers DESC"
    )
    df = database.run_query(sql, params=params)
    return normalize.normalize_dataframe(df)


def get_cell_centroid_overlay() -> pd.DataFrame:
    """Privacy-safe overlay: one centroid per serving cell (grid averages)."""
    df = database.run_query(
        "SELECT serving_cell_id AS cell_id, "
        "       COUNT(*) AS addresses, "
        "       ROUND(AVG(latitude)::numeric, 4) AS lat, "
        "       ROUND(AVG(longitude)::numeric, 4) AS lon, "
        "       COUNT(DISTINCT governorate) AS governorates "
        "FROM cleaned_data.t4_coverage_address_grid "
        "GROUP BY serving_cell_id ORDER BY addresses DESC",
        {},
    )
    return normalize.normalize_dataframe(df)


def get_grid_summary() -> Dict[str, Any]:
    """Live address-grid summary (aggregates only)."""
    df = database.run_query(
        "SELECT COUNT(*) AS points, "
        "       COUNT(DISTINCT serving_cell_id) AS cells, "
        "       COUNT(DISTINCT governorate) AS governorates "
        "FROM cleaned_data.t4_coverage_address_grid",
        {},
    )
    return {col: int(df.iloc[0][col]) for col in df.columns}


def is_geo_join_verified() -> Dict[str, Any]:
    """Coverage-map gate: subscriber->grid join must be complete (12,412)."""
    df = database.run_query(
        "SELECT COUNT(*) AS joined FROM cleaned_data.abt_subscriber_month a "
        "JOIN cleaned_data.t4_coverage_address_grid g "
        "ON g.address_id = a.address_id",
        {},
    )
    matched = int(df.iloc[0]["joined"])
    verified = matched == 12412
    return {"verified": verified, "matched": matched, "expected": 12412}
