"""Build and validate the public subscriber-month Analytical Base Table."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import pandas as pd
import duckdb


SOURCE_TABLES = (
    "crm_subscribers",
    "usage_monthly",
    "coverage_addresses",
    "service_consumption",
    "cell_kpis",
)


def load_source_dataset(source_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load the five generated source tables from a Parquet directory."""
    source_path = Path(source_dir)
    dataset = {
        table_name: pd.read_parquet(source_path / f"{table_name}.parquet")
        for table_name in SOURCE_TABLES
    }
    return dataset


def build_abt(dataset: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Join source tables with DuckDB SQL into one analytical base."""
    missing = set(SOURCE_TABLES).difference(dataset)
    if missing:
        raise ValueError(f"Missing source tables: {sorted(missing)}")

    connection = duckdb.connect()
    try:
        for table_name in SOURCE_TABLES:
            connection.register(table_name, dataset[table_name])
        query = """
        WITH joined AS (
            SELECT
                c.subscriber_id, c.snapshot_month, c.segment_tier,
                c.b2b_b2c_flag, c.arpu_monthly_tnd, c.tenure_months,
                c.address_id, c.governorate, c.contract_type,
                c.num_active_lines, c.churn,
                u.monthly_sessions, u.monthly_total_gb,
                u.monthly_peak_hour_ratio, u.dominant_device_generation,
                u.dominant_serving_cell_id, u.device_5g_ready_flag,
                cov.serving_cell_id, cov.latitude, cov.longitude,
                cov.predicted_rsrp_dbm, cov.predicted_sinr_db,
                cov.coverage_5g_flag, cov.coverage_4g_flag,
                cov.fiber_coverage_flag, cov.signal_quality_class,
                cov.radio_feasibility_class,
                s.streaming_vol_gb, s.streaming_session_count,
                s.iptv_active_flag, s.iptv_watch_hours, s.voip_minutes,
                s.gaming_vol_gb,
                k.site_id, k.avg_prb_utilisation_pct,
                k.p95_prb_utilisation_pct, k.max_prb_utilisation_pct,
                k.avg_dl_throughput_mbps
            FROM crm_subscribers AS c
            INNER JOIN usage_monthly AS u
                ON c.subscriber_id = u.subscriber_id
               AND c.snapshot_month = u.snapshot_month
            INNER JOIN service_consumption AS s
                ON c.subscriber_id = s.subscriber_id
               AND c.snapshot_month = s.snapshot_month
            INNER JOIN coverage_addresses AS cov
                ON c.address_id = cov.address_id
            INNER JOIN cell_kpis AS k
                ON u.dominant_serving_cell_id = k.cell_id
               AND u.snapshot_month = k.snapshot_month
        )
        SELECT
            joined.*,
            CASE
                WHEN arpu_monthly_tnd <= 25 THEN 'LV'
                WHEN arpu_monthly_tnd <= 55 THEN 'Mid'
                WHEN arpu_monthly_tnd <= 90 THEN 'High'
                ELSE 'Premium'
            END AS arpu_band,
            CASE
                WHEN tenure_months <= 12 THEN 'Short Tenure'
                WHEN tenure_months <= 36 THEN 'Medium Tenure'
                ELSE 'Long Tenure'
            END AS tenure_band,
            num_active_lines > 1 AS multi_line_flag,
            streaming_vol_gb >= quantile_cont(streaming_vol_gb, 0.75) OVER () AS streaming_heavy_flag,
            gaming_vol_gb >= quantile_cont(gaming_vol_gb, 0.75) OVER () AS gaming_heavy_flag,
            voip_minutes >= quantile_cont(voip_minutes, 0.75) OVER () AS high_voip_usage_flag,
            CASE WHEN p95_prb_utilisation_pct <= 80 THEN 'Available' ELSE 'Constrained' END
                AS current_capacity_proxy_status
        FROM joined
        """
        return connection.execute(query).df()
    finally:
        connection.close()


def validate_abt(abt: pd.DataFrame) -> None:
    """Raise ValueError when the ABT violates its public grain contract."""
    required = {
        "subscriber_id",
        "snapshot_month",
        "address_id",
        "dominant_serving_cell_id",
        "arpu_band",
        "tenure_band",
        "multi_line_flag",
        "p95_prb_utilisation_pct",
        "current_capacity_proxy_status",
    }
    missing = required.difference(abt.columns)
    if missing:
        raise ValueError(f"ABT is missing columns: {sorted(missing)}")
    if abt[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("ABT grain must be unique by subscriber and snapshot")
    if abt["subscriber_id"].isna().any() or abt["address_id"].isna().any():
        raise ValueError("ABT keys cannot be null")
    if not abt["p95_prb_utilisation_pct"].between(0, 100).all():
        raise ValueError("ABT PRB utilisation must be between 0 and 100")
    if not set(abt["current_capacity_proxy_status"]).issubset({"Available", "Constrained"}):
        raise ValueError("ABT contains an invalid capacity status")


def save_abt(abt: pd.DataFrame, output_dir: str | Path) -> dict:
    """Validate and persist the ABT and a compact transformation manifest."""
    validate_abt(abt)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    abt.to_parquet(output_path / "abt_subscriber_month.parquet", index=False)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "table": "abt_subscriber_month",
        "grain": ["subscriber_id", "snapshot_month"],
        "rows": len(abt),
        "columns": list(abt.columns),
    }
    (output_path / "abt_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
