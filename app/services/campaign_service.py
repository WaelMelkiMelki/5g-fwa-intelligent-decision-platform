"""Campaign Operations service — paginated, sortable subscriber table + export.

Table query uses SQL LIMIT/OFFSET pagination with sorting on allowlisted
columns. The export pulls the full filtered population (capped) and applies
column whitelisting + identifier masking (see business_logic.masking).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.business_logic import filtering, masking
from app.services import database
from app.services.executive_service import BASE_JOIN_SQL, BASE_SUBSET_COLUMNS

SORTABLE_COLUMNS = {
    "final_priority_score",
    "fwa_suitability_score",
    "churn_probability",
    "arpu_monthly_tnd",
    "tenure_months",
    "num_active_lines",
    "candidate_prioritization_score",
}

CAMPAIGN_TABLE_COLUMNS = [
    "s.subscriber_id",
    "s.fwa_suitability_score",
    "s.fwa_suitability_band",
    "s.churn_risk_band",
    "s.churn_probability",
    "s.recommended_offer",
    "s.offer_category",
    "s.final_priority_score",
    "s.final_priority_band",
    "s.campaign_action",
    "s.rollout_status",
    "s.post_migration_capacity_risk",
    "s.cluster_id",
    "s.business_label",
    "a.governorate",
]


def _where(filters: Dict[str, Any], snapshot: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    predicates, params = filtering.build_predicates(filters, snapshot)
    return filtering.build_where_clause(predicates), params


def get_subscribers(
    filters: Dict[str, Any],
    page: int = 1,
    page_size: int = 50,
    sort_column: str = "final_priority_score",
    sort_desc: bool = True,
    snapshot: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated campaign table page (rows + total count)."""
    page = max(1, int(page))
    page_size = min(max(10, int(page_size)), 500)
    if sort_column not in SORTABLE_COLUMNS:
        sort_column = "final_priority_score"
    order = "DESC" if sort_desc else "ASC"
    where_clause, params = _where(filters, snapshot)

    count_sql = "SELECT COUNT(*) AS n " + BASE_JOIN_SQL + where_clause
    rows_sql = (
        "SELECT " + ", ".join(CAMPAIGN_TABLE_COLUMNS) + " " + BASE_JOIN_SQL
        + where_clause
        + f" ORDER BY s.{sort_column} {order} NULLS LAST"
        + f" LIMIT {int(page_size)} OFFSET {int((page - 1) * page_size)}"
    )
    n = int(database.run_query(count_sql, params=params).iloc[0]["n"])
    rows = database.run_query(rows_sql, params=params)
    # Note: rows keep the REAL subscriber_id here; masking happens in the UI
    # layer (page 2 masks the displayed copy). The real id is needed by the
    # page to build the drill-down mapping (masked id -> real id).
    return {"rows": rows, "total": n, "page": page, "page_size": page_size}


def get_export_rows(
    filters: Dict[str, Any],
    snapshot: Optional[str] = None,
    max_rows: int = 200_000,
) -> pd.DataFrame:
    """Full filtered population for export (masked, whitelisted columns)."""
    predicates, params = filtering.build_predicates(filters, snapshot)
    sql = (
        "SELECT " + ", ".join(BASE_SUBSET_COLUMNS) + " " + BASE_JOIN_SQL
        + filtering.build_where_clause(predicates)
        + f" ORDER BY s.final_priority_score DESC NULLS LAST LIMIT {int(max_rows)}"
    )
    df = database.run_query(sql, params=params)
    export_df, _ = masking.strip_and_mask_for_export(df)
    return export_df


def export_csv_bytes(
    filters: Dict[str, Any],
    snapshot: Optional[str] = None,
    page_slug: str = "campaign",
) -> Tuple[bytes, str, int]:
    """Return (csv_bytes, filename, row_count) with UTF-8 BOM and masked fields.

    Filename: ``fwa_<page_slug>_<snapshot_yyyymm>_<hash>.csv`` per spec I6.
    """
    df = get_export_rows(filters, snapshot)
    if df.empty:
        raise ValueError("Nothing to export for the current filters")
    content = df.to_csv(index=False).encode("utf-8-sig")
    stamp = "202601"
    if snapshot and len(snapshot) >= 7:
        stamp = snapshot[:4] + snapshot[5:7]
    token = hashlib.sha256(content).hexdigest()[:8]
    filename = f"fwa_{page_slug}_{stamp}_{token}.csv"
    return content, filename, int(len(df))
