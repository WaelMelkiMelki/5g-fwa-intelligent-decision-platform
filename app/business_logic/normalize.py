"""Type normalization registry (DECISION 8).

Database types are NEVER altered. Normalization happens only in the Python
service layer after SQL retrieval, per the registry documented in
SCHEMA_MAPPING.md §8:

- ``cluster_id``            -> nullable pandas Int64 (int8->int4 across sources)
- numeric metric fields     -> pandas numeric (float)
- ``activation_date``       -> pandas datetime
- ``snapshot_month``        -> pandas datetime (filters display YYYY-MM-DD)
- categorical NULL/sentinel -> explicit UI labels ONLY at display time,
                               never inside SQL predicates (see
                               business_logic/display.py)

SQL predicates stay bound to the actual database values.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

# step15.cluster_id / step11.cluster_id are int8; abt_subscriber_month_clustered
# is int4. Sentinel value -1 (Excluded) is preserved; absent values stay NULL/NaN.
CLUSTER_COLUMNS = ("cluster_id",)

# Float/int metric columns normalized to float64 (whole-ABT and eligible-level).
NUMERIC_COLUMNS = (
    "arpu_monthly_tnd",
    "tenure_months",
    "num_active_lines",
    "fwa_suitability_score",
    "candidate_prioritization_score",
    "suitability_based_ranking",
    "churn_probability",
    "Base_Score",
    "final_priority_score",
    "p95_prb_utilisation_pct",
    "avg_prb_utilisation_pct",
    "max_prb_utilisation_pct",
    "avg_dl_throughput_mbps",
    "monthly_sessions",
    "monthly_total_gb",
    "dl_volume_mb_imputed_monthly_median",
    "monthly_peak_hour_ratio",
    "predicted_rsrp_dbm",
    "predicted_sinr_db",
    "streaming_vol_gb",
    "streaming_session_count",
    "iptv_watch_hours",
    "voip_minutes",
    "iot_traffic_share_pct",
    "social_media_vol_gb",
    "gaming_vol_gb",
    "expected_additional_prb_proxy",
    "post_migration_prb_utilisation_proxy",
    "distance_to_cell_km",
    "fwa_raw_score",
)

SNAPSHOT_COLUMNS = ("snapshot_month", "activation_date")

DATETIME_COLUMNS = ("activation_date",)

# Registered per-service column sets: subsets read by the app layer.
APP_NUMERIC_COLUMNS = (
    "arpu_monthly_tnd",
    "tenure_months",
    "num_active_lines",
    "fwa_suitability_score",
    "candidate_prioritization_score",
    "churn_probability",
    "Base_Score",
    "final_priority_score",
    "p95_prb_utilisation_pct",
    "avg_prb_utilisation_pct",
    "max_prb_utilisation_pct",
    "avg_dl_throughput_mbps",
    "monthly_sessions",
    "monthly_total_gb",
    "monthly_peak_hour_ratio",
    "predicted_rsrp_dbm",
    "predicted_sinr_db",
    "streaming_vol_gb",
    "iptv_watch_hours",
    "voip_minutes",
    "iot_traffic_share_pct",
    "social_media_vol_gb",
    "gaming_vol_gb",
    "expected_additional_prb_proxy",
    "post_migration_prb_utilisation_proxy",
    "distance_to_cell_km",
    "fwa_raw_score",
)


def cluster_series(series: pd.Series) -> pd.Series:
    """Normalize cluster_id to nullable Int64 (int8/int4 -> Int64)."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def numeric_series(series: pd.Series) -> pd.Series:
    """Normalize a numeric metric column to float64 (NULL preserved)."""
    return pd.to_numeric(series, errors="coerce")


def datetime_series(series: pd.Series) -> pd.Series:
    """Normalize a timestamp column to pandas datetime."""
    return pd.to_datetime(series, errors="coerce")


def normalize_dataframe(
    df: pd.DataFrame,
    *,
    clusters: bool = True,
    numeric: bool = True,
    datetimes: bool = True,
) -> pd.DataFrame:
    """Apply the §8 registry to a freshly read DataFrame (non-mutating)."""
    out = df.copy()
    if clusters and "cluster_id" in out.columns:
        out["cluster_id"] = cluster_series(out["cluster_id"])
    if numeric:
        for col in out.columns:
            if col in APP_NUMERIC_COLUMNS or col in NUMERIC_COLUMNS:
                out[col] = numeric_series(out[col])
    if datetimes:
        for col in out.columns:
            if col == "activation_date":
                out[col] = datetime_series(out[col])
    return out


def snapshot_to_string(value: object) -> Optional[str]:
    """Format a snapshot_month value as YYYY-MM-DD (or None)."""
    if value is None or pd.isna(value):
        return None
    ts = pd.Timestamp(value)
    return ts.strftime("%Y-%m-%d")
