"""Network Capacity service — cell summary, headroom, subscriber mix, cells.

Sources: ``t3_cell_monthly_kpi`` (verified 731 cells), ``step14_capacity_simulation``
(2,923 rows), and cell centroids from ``t4_coverage_address_grid`` (only
lat/lon source — verified).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.business_logic import guards
from app.services import database

CELL_COLUMNS = [
    "c.cell_id",
    "c.site_id",
    "c.snapshot_month",
    "c.avg_prb_utilisation_pct",
    "c.p95_prb_utilisation_pct",
    "c.max_prb_utilisation_pct",
    "c.avg_dl_throughput_mbps",
    "c.current_capacity_proxy_status",
]

SORTABLE = {
    "p95_prb_utilisation_pct",
    "max_prb_utilisation_pct",
    "avg_prb_utilisation_pct",
    "cell_id",
    "subscriber_count",
}


def get_all_cells(snapshot: Optional[str] = None) -> pd.DataFrame:
    """All cells with KPIs (no subscriber filtering)."""
    where = ""
    params: Dict[str, Any] = {}
    if snapshot is not None:
        where = " WHERE c.snapshot_month = :snapshot_month"
        params = {"snapshot_month": snapshot}
    sql = (
        "SELECT " + ", ".join(CELL_COLUMNS)
        + " FROM cleaned_data.t3_cell_monthly_kpi c" + where
        + " ORDER BY c.p95_prb_utilisation_pct DESC NULLS LAST"
    )
    return database.run_query(sql, params=params)


def get_capacity_summary() -> Dict[str, Any]:
    """Cell-level KPIs of the whole grid (capacity page header)."""
    cells = get_all_cells()
    empty = {
        "cells_total": 0,
        "status_distribution": {},
        "p95_max": None,
        "p95_mean": None,
        "at_prb_threshold": 0,
    }
    if cells.empty:
        return empty
    p95 = cells["p95_prb_utilisation_pct"]
    status = cells["current_capacity_proxy_status"].fillna("(None)").value_counts().to_dict()
    return {
        "cells_total": int(len(cells)),
        "status_distribution": status,
        "p95_max": float(p95.max()),
        "p95_mean": float(p95.mean()),
        "at_prb_threshold": int((p95 >= 80.0).sum()),
    }


def get_cells_table(
    page: int = 1,
    page_size: int = 50,
    sort_column: str = "p95_prb_utilisation_pct",
    sort_desc: bool = True,
    snapshot: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated cell KPI table joined with subscriber counts (step14)."""
    page = max(1, int(page))
    page_size = min(max(10, int(page_size)), 500)
    if sort_column not in SORTABLE:
        sort_column = "p95_prb_utilisation_pct"
    safe_col = sort_column  # from allowlist
    order = "DESC" if sort_desc else "ASC"
    guards.ensure_single_snapshot(database.run_query)
    guards.ensure_join_keys_unique(
        database.run_query, sources=(("step14_capacity_simulation", "subscriber_id"),)
    )

    count_col = "c.p95_prb_utilisation_pct" if safe_col == "p95_prb_utilisation_pct" else (
        "c.max_prb_utilisation_pct" if safe_col == "max_prb_utilisation_pct"
        else "c.avg_prb_utilisation_pct" if safe_col == "avg_prb_utilisation_pct"
        else "c.cell_id"
    )
    order_expr = count_col + f" {order} NULLS LAST" if safe_col != "subscriber_count" else f"t.subscriber_count {order} NULLS LAST"

    where = ""
    params: Dict[str, Any] = {}
    if snapshot is not None:
        where = " WHERE c.snapshot_month = :snapshot_month"
        params = {"snapshot_month": snapshot}

    order_by_col = order_expr
    sql = f"""
        SELECT c.cell_id, c.site_id, c.snapshot_month,
               c.avg_prb_utilisation_pct, c.p95_prb_utilisation_pct,
               c.max_prb_utilisation_pct, c.avg_dl_throughput_mbps,
               c.current_capacity_proxy_status,
               COALESCE(t.subscriber_count, 0) AS subscriber_count
        FROM cleaned_data.t3_cell_monthly_kpi c
        LEFT JOIN (
            SELECT dominant_serving_cell_id AS cell_id, COUNT(*) AS subscriber_count
            FROM cleaned_data.step14_capacity_simulation
            WHERE dominant_serving_cell_id IS NOT NULL
            GROUP BY dominant_serving_cell_id
        ) t ON t.cell_id = c.cell_id
        {where}
        ORDER BY {order_by_col}
        LIMIT :limit OFFSET :offset
    """
    params.update({"limit": int(page_size), "offset": int((page - 1) * page_size)})
    rows = database.run_query(sql, params=params)

    count_sql = (
        "SELECT COUNT(*) AS n FROM cleaned_data.t3_cell_monthly_kpi c" + where
    )
    params_count = {"snapshot_month": snapshot} if snapshot else {}
    n = int(database.run_query(count_sql, params=params_count).iloc[0]["n"])
    return {"rows": rows, "total": n, "page": page, "page_size": page_size}


def get_cell_subscribers(cell_id: str, limit: int = 20) -> pd.DataFrame:
    """Top-N subscribers served by a cell (masked at return)."""
    guards.ensure_single_snapshot(database.run_query)
    guards.ensure_join_keys_unique(
        database.run_query, sources=(("step14_capacity_simulation", "subscriber_id"),)
    )
    sql = """
    SELECT s.subscriber_id, s.fwa_suitability_score, s.fwa_suitability_band,
           s.churn_risk_band, s.final_priority_score, s.campaign_action,
           a.governorate
    FROM cleaned_data.step14_capacity_simulation d
    JOIN cleaned_data.step15_final_campaign_list s
      ON s.subscriber_id = d.subscriber_id
    JOIN cleaned_data.abt_subscriber_month a
      ON a.subscriber_id = s.subscriber_id AND a.snapshot_month = s.snapshot_month
    WHERE d.dominant_serving_cell_id = :cell_id
    ORDER BY s.final_priority_score DESC NULLS LAST
    LIMIT :limit
    """
    df = database.run_query(
        sql, params={"cell_id": str(cell_id), "limit": int(limit)}
    )
    from app.business_logic import masking

    masking.mask_dataframe_identifiers(df)
    return df


def get_cell_subscriber_count(cell_id: str) -> int:
    """Count of step14 (eligible) subscribers on a cell."""
    guards.ensure_join_keys_unique(
        database.run_query, sources=(("step14_capacity_simulation", "subscriber_id"),)
    )
    df = database.run_query(
        """
        SELECT COUNT(*) AS n
        FROM cleaned_data.step14_capacity_simulation
        WHERE dominant_serving_cell_id = :cell_id
        """,
        params={"cell_id": str(cell_id)},
    )
    return int(df.iloc[0]["n"]) if not df.empty else 0


def get_cell_geo() -> pd.DataFrame:
    """Cell centroids from the address grid (only lat/lon source, verified)."""
    sql = """
    SELECT g.serving_cell_id AS cell_id,
           AVG(g.latitude)  AS latitude,
           AVG(g.longitude) AS longitude,
           COUNT(*)         AS address_count
    FROM cleaned_data.t4_coverage_address_grid g
    WHERE g.latitude IS NOT NULL AND g.longitude IS NOT NULL
    GROUP BY g.serving_cell_id
    """
    return database.run_query(sql)
