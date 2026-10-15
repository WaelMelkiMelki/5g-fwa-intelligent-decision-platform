"""Subscriber Drill-Down service — full masked profile for one subscriber.

Per interaction spec I4: joins the step chain (ABT + churn + offers +
capacity + campaign + coverage/geo) into one masked profile. No PII is ever
selected (msisdn lives only in daily T1 — never queried here).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from app.business_logic import guards, masking
from app.services import database

PROFILE_SQL = """
SELECT
    s.subscriber_id,
    s.snapshot_month,
    s.fwa_suitability_score,
    s.fwa_suitability_band,
    s.fwa_exclusion_reason,
    s.churn_probability,
    s.churn_risk_band,
    s.offer_category,
    s.recommended_offer,
    s.final_priority_score,
    s.final_priority_band,
    s.campaign_action,
    s.rollout_status,
    s.post_migration_capacity_risk,
    s.cluster_id,
    s.business_label,
    s.num_active_lines,
    s.contract_type,
    s.segment_tier,
    s.arpu_monthly_tnd,
    s.tenure_months,
    a.address_id,
    a.governorate,
    a.signal_quality_class,
    a.radio_feasibility_class,
    a.current_capacity_proxy_status,
    a.dominant_serving_cell_id,
    a.monthly_total_gb,
    a.handset_5g_ready_flag,
    a.streaming_heavy_flag,
    a.gaming_heavy_flag,
    a.high_voip_usage_flag,
    r.tier1_base_plan,
    r.tier2_addons,
    r.reason_codes,
    d.post_migration_prb_utilisation_proxy,
    d.expected_additional_prb_proxy
FROM cleaned_data.step15_final_campaign_list s
JOIN cleaned_data.abt_subscriber_month a
  ON s.subscriber_id = a.subscriber_id AND s.snapshot_month = a.snapshot_month
LEFT JOIN cleaned_data.step13_recommendations r
  ON s.subscriber_id = r.subscriber_id
LEFT JOIN cleaned_data.step14_capacity_simulation d
  ON s.subscriber_id = d.subscriber_id
WHERE s.subscriber_id = :subscriber_id
"""


def get_subscriber_details(subscriber_id: str, snapshot: Optional[str] = None) -> Dict[str, Any]:
    """Fetch and mask the full profile for one subscriber.

    Returns a dict with 'profile' (masked single-row DataFrame) and 'found'
    bool. When the ID does not exist, returns an empty profile.
    """
    if not subscriber_id or not isinstance(subscriber_id, str):
        raise ValueError("subscriber_id must be a non-empty string")
    guards.ensure_single_snapshot(database.run_query)
    guards.ensure_join_keys_unique(database.run_query)
    if snapshot is not None:
        sql = PROFILE_SQL + " AND s.snapshot_month = :snapshot_month"
        params = {"subscriber_id": subscriber_id, "snapshot_month": snapshot}
    else:
        sql, params = PROFILE_SQL, {"subscriber_id": subscriber_id}

    df = database.run_query(sql, params=params)
    if df.empty:
        return {"profile": pd.DataFrame(), "found": False}
    masking.mask_dataframe_identifiers(df)
    return {"profile": df.iloc[[0]].copy(), "found": True}


def search_subscribers(term: str, limit: int = 20) -> pd.DataFrame:
    """Case-insensitive prefix search on real subscriber_id.

    Returns a DataFrame with the REAL ``subscriber_id`` (used only to resolve
    selection internally) plus a masked ``subscriber_id_masked`` column for
    display. Callers must never render the real column.
    """
    term = (term or "").strip()
    if not term:
        return pd.DataFrame(columns=["subscriber_id", "subscriber_id_masked", "governorate"])
    guards.ensure_single_snapshot(database.run_query)
    sql = """
    SELECT DISTINCT s.subscriber_id, a.governorate
    FROM cleaned_data.step15_final_campaign_list s
    JOIN cleaned_data.abt_subscriber_month a
      ON s.subscriber_id = a.subscriber_id AND s.snapshot_month = a.snapshot_month
    WHERE s.subscriber_id ILIKE :pattern
    ORDER BY s.subscriber_id
    LIMIT :limit
    """
    df = database.run_query(
        sql, params={"pattern": f"%{term}%", "limit": int(limit)}
    )
    df["subscriber_id_masked"] = df["subscriber_id"].map(masking.mask_subscriber_id)
    return df
