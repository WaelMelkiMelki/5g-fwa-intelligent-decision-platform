"""Customer Segmentation service — persona aggregation from the CLUSTERED table.

Source of truth: ``cleaned_data.abt_subscriber_month_clustered`` (precomputed
clustering, step10) joined to the final-campaign list. The app never trains or
re-runs clustering; it only reads the stored ``cluster_id`` and
``business_label`` columns (no invented labels).

``cluster_id = -1`` is the stored sentinel for Not-Segmented (Excluded
population); the display layer maps it via ``display.apply_sentinel_labels``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.business_logic import filtering, guards, normalize
from app.services import database

# Explicit column set (no SELECT *). k = clustered alias.
SEGMENT_COLUMNS: List[str] = [
    "k.subscriber_id",
    "k.cluster_id",
    "k.business_label",
    "k.arpu_monthly_tnd",
    "k.monthly_total_gb",
    "k.streaming_vol_gb",
    "k.gaming_vol_gb",
    "k.voip_minutes",
    "k.tenure_months",
    "k.contract_type",
    "k.arpu_band",
    "k.tenure_band",
    "k.segment_tier",
    "k.handset_5g_ready_flag",
    "k.multi_line_flag",
]

# Verified cross-tab dimensions (SCHEMA_MAPPING.md §4): column -> display name.
CROSS_TAB_DIMENSIONS: Dict[str, str] = {
    "contract_type": "Contract type",
    "arpu_band": "ARPU band",
    "tenure_band": "Tenure band",
    "segment_tier": "Segment tier",
    "handset_5g_ready_flag": "5G-ready handset",
    "multi_line_flag": "Multi-line flag",
}

CLUSTERED_JOIN_SQL = (
    "FROM cleaned_data.step15_final_campaign_list s "
    "JOIN cleaned_data.abt_subscriber_month_clustered k "
    "ON k.subscriber_id = s.subscriber_id"
)


def _clustered_subset(
    filters: Dict[str, Any],
    snapshot: Optional[str] = None,
) -> pd.DataFrame:
    """Eligible subscribers joined with their precomputed segment attributes."""
    guards.ensure_single_snapshot(database.run_query)
    predicates, params = filtering.build_predicates(filters, snapshot)
    where = " WHERE " + " AND ".join(predicates) if predicates else ""
    sql = (
        "SELECT " + ", ".join(SEGMENT_COLUMNS) + " " + CLUSTERED_JOIN_SQL
        + where + " ORDER BY k.cluster_id"
    )
    df = database.run_query(sql, params=params)
    return normalize.normalize_dataframe(df)


def get_cluster_summary(
    filters: Dict[str, Any], snapshot: Optional[str] = None
) -> pd.DataFrame:
    """Per-cluster summary: size + mean ARPU/GB (+ streaming/gaming)/tenure."""
    df = _clustered_subset(filters, snapshot)
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(["cluster_id", "business_label"], dropna=False).agg(
        subscribers=("subscriber_id", "count"),
        mean_arpu=("arpu_monthly_tnd", "mean"),
        mean_gb=("monthly_total_gb", "mean"),
        mean_streaming_gb=("streaming_vol_gb", "mean"),
        mean_gaming_gb=("gaming_vol_gb", "mean"),
        median_tenure=("tenure_months", "median"),
    ).reset_index()
    return grouped.sort_values("subscribers", ascending=False).reset_index(drop=True)


def get_segment_cross_tab(
    filters: Dict[str, Any],
    dimension: str,
    snapshot: Optional[str] = None,
) -> pd.DataFrame:
    """Cluster x dimension pivot (counts; stored dimension labels)."""
    if dimension not in CROSS_TAB_DIMENSIONS:
        raise ValueError(f"Unsupported cross-tab dimension: {dimension!r}")
    df = _clustered_subset(filters, snapshot)
    if df.empty:
        return pd.DataFrame()
    pivot = (
        df.groupby([dimension, "cluster_id"], dropna=False)
        .size()
        .reset_index(name="count")
        .pivot(index=dimension, columns="cluster_id", values="count")
        .fillna(0)
        .astype(int)
    )
    return pivot.reset_index()


def get_dimension_options() -> Dict[str, str]:
    """Catalog of verified cross-tab dimensions (no dynamic SQL columns)."""
    return dict(CROSS_TAB_DIMENSIONS)
