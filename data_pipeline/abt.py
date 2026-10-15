"""Build and validate the public subscriber-month Analytical Base Table."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import pandas as pd


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


def _add_distribution_features(abt: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic bands and service-intensity flags to the joined base."""
    abt = abt.copy()
    abt["arpu_band"] = pd.cut(
        abt["arpu_monthly_tnd"],
        bins=[-float("inf"), 25, 55, 90, float("inf")],
        labels=["LV", "Mid", "High", "Premium"],
    ).astype(str)
    abt["tenure_band"] = pd.cut(
        abt["tenure_months"],
        bins=[-float("inf"), 12, 36, float("inf")],
        labels=["Short Tenure", "Medium Tenure", "Long Tenure"],
    ).astype(str)
    abt["multi_line_flag"] = abt["num_active_lines"] > 1
    abt["streaming_heavy_flag"] = abt["streaming_vol_gb"] >= abt["streaming_vol_gb"].quantile(0.75)
    abt["gaming_heavy_flag"] = abt["gaming_vol_gb"] >= abt["gaming_vol_gb"].quantile(0.75)
    abt["high_voip_usage_flag"] = abt["voip_minutes"] >= abt["voip_minutes"].quantile(0.75)
    abt["current_capacity_proxy_status"] = (
        abt["p95_prb_utilisation_pct"] <= 80
    ).map({True: "Available", False: "Constrained"})
    return abt


def build_abt(dataset: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Join validated source tables into one subscriber-month analytical base."""
    missing = set(SOURCE_TABLES).difference(dataset)
    if missing:
        raise ValueError(f"Missing source tables: {sorted(missing)}")

    crm = dataset["crm_subscribers"].copy()
    usage = dataset["usage_monthly"].copy()
    coverage = dataset["coverage_addresses"].copy()
    services = dataset["service_consumption"].copy()
    cells = dataset["cell_kpis"].copy()

    abt = crm.merge(
        usage,
        on=["subscriber_id", "snapshot_month"],
        how="inner",
        validate="one_to_one",
        suffixes=("", "_usage"),
    )
    abt = abt.merge(
        services,
        on=["subscriber_id", "snapshot_month"],
        how="inner",
        validate="one_to_one",
    )
    abt = abt.merge(
        coverage,
        on="address_id",
        how="inner",
        validate="one_to_one",
        suffixes=("", "_coverage"),
    )
    abt = abt.merge(
        cells,
        left_on=["dominant_serving_cell_id", "snapshot_month"],
        right_on=["cell_id", "snapshot_month"],
        how="inner",
        validate="many_to_one",
        suffixes=("", "_cell"),
    ).drop(columns=["cell_id"])
    return _add_distribution_features(abt)


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
