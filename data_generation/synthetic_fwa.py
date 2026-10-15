"""Generate a small, relational synthetic telecom environment.

The generator is intentionally independent of PostgreSQL. It produces the five
source domains used by the original pipeline and keeps identifiers synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticFwaConfig:
    """Controls dataset size, snapshot, seed, and optional quality defects."""

    subscribers: int = 12412
    cells: int = 731
    snapshot_month: str = "2026-01-01"
    seed: int = 42
    inject_anomalies: bool = False


def _choice(rng: np.random.Generator, values: list[str], size: int) -> np.ndarray:
    return rng.choice(values, size=size)


def generate_dataset(config: SyntheticFwaConfig | None = None) -> Dict[str, pd.DataFrame]:
    """Return five related source tables with reproducible synthetic values."""
    config = config or SyntheticFwaConfig()
    if config.subscribers < 1 or config.cells < 1:
        raise ValueError("subscribers and cells must be positive")

    rng = np.random.default_rng(config.seed)
    snapshot = pd.Timestamp(config.snapshot_month).normalize()
    subscriber_ids = np.array([f"SUB_{i:06d}" for i in range(config.subscribers)])
    cell_ids = np.array([f"CELL_{i:04d}" for i in range(config.cells)])
    address_ids = np.array([f"ADDR_{i:06d}" for i in range(config.subscribers)])
    governorates = np.array(["Tunis", "Ariana", "Sousse", "Sfax", "Nabeul", "Bizerte"])
    cell_for_address = rng.choice(cell_ids, size=config.subscribers)
    site_for_cell = {cell: f"SITE_{index // 2:04d}" for index, cell in enumerate(cell_ids)}
    governorate_for_address = rng.choice(governorates, size=config.subscribers)

    arpu = np.clip(rng.lognormal(mean=3.25, sigma=0.42, size=config.subscribers), 8, 180)
    tenure = rng.integers(1, 96, size=config.subscribers)
    monthly_gb = np.clip(rng.lognormal(mean=2.0, sigma=0.8, size=config.subscribers), 0.2, 250)
    active_lines = rng.choice([1, 2, 3, 4], size=config.subscribers, p=[0.72, 0.18, 0.07, 0.03])
    contract_type = _choice(rng, ["Prepaid", "Postpaid", "Hybrid"], config.subscribers)
    five_g_ready = rng.random(config.subscribers) < 0.42
    churn_logit = -3.0 + 0.018 * (35 - arpu) + 0.008 * (24 - tenure) + 0.25 * (contract_type == "Prepaid")
    churn_probability = 1 / (1 + np.exp(-churn_logit))

    crm = pd.DataFrame(
        {
            "subscriber_id": subscriber_ids,
            "snapshot_month": snapshot,
            "segment_tier": pd.cut(arpu, [-np.inf, 25, 55, 90, np.inf], labels=["LV", "Mid", "High", "Premium"]).astype(str),
            "b2b_b2c_flag": _choice(rng, ["B2C", "B2B"], config.subscribers),
            "arpu_monthly_tnd": arpu.round(2),
            "tenure_months": tenure,
            "address_id": address_ids,
            "governorate": governorate_for_address,
            "contract_type": contract_type,
            "num_active_lines": active_lines,
            "churn": (rng.random(config.subscribers) < churn_probability).astype(int),
        }
    )

    usage = pd.DataFrame(
        {
            "subscriber_id": subscriber_ids,
            "snapshot_month": snapshot,
            "monthly_sessions": np.maximum(rng.poisson(90, config.subscribers), 1),
            "monthly_total_gb": monthly_gb.round(3),
            "monthly_peak_hour_ratio": np.clip(rng.normal(0.34, 0.09, config.subscribers), 0.05, 0.85).round(3),
            "dominant_device_generation": _choice(rng, ["4G", "5G"], config.subscribers),
            "dominant_serving_cell_id": cell_for_address,
            "device_5g_ready_flag": five_g_ready,
        }
    )

    coverage_quality = rng.choice(["Poor", "Acceptable", "Excellent"], config.subscribers, p=[0.28, 0.52, 0.20])
    rsrp_by_quality = {"Poor": -112, "Acceptable": -96, "Excellent": -78}
    rsrp = np.array([rsrp_by_quality[value] for value in coverage_quality]) + rng.normal(0, 5, config.subscribers)
    sinr = np.clip((rsrp + 115) / 3 + rng.normal(0, 2, config.subscribers), -10, 30)
    coverage_5g = rsrp > -100
    fiber = rng.random(config.subscribers) < 0.08
    coverage = pd.DataFrame(
        {
            "address_id": address_ids,
            "serving_cell_id": cell_for_address,
            "latitude": rng.uniform(35.6, 36.9, config.subscribers).round(6),
            "longitude": rng.uniform(8.5, 11.2, config.subscribers).round(6),
            "governorate": governorate_for_address,
            "predicted_rsrp_dbm": rsrp.round(2),
            "predicted_sinr_db": sinr.round(2),
            "coverage_5g_flag": coverage_5g,
            "coverage_4g_flag": np.ones(config.subscribers, dtype=bool),
            "fiber_coverage_flag": fiber,
            "signal_quality_class": coverage_quality,
            "radio_feasibility_class": np.select(
                [fiber, rsrp <= -105, coverage_5g],
                ["Fiber_Competitor", "Infeasible", "5G_Feasible"],
                default="4G_Fallback",
            ),
        }
    )

    service = pd.DataFrame(
        {
            "subscriber_id": subscriber_ids,
            "snapshot_month": snapshot,
            "streaming_vol_gb": (monthly_gb * rng.uniform(0.05, 0.45, config.subscribers)).round(3),
            "streaming_session_count": rng.poisson(18, config.subscribers),
            "iptv_active_flag": rng.random(config.subscribers) < 0.14,
            "iptv_watch_hours": np.clip(rng.gamma(2.0, 3.5, config.subscribers), 0, 60).round(2),
            "voip_minutes": np.clip(rng.gamma(2.0, 35, config.subscribers), 0, 500).round(2),
            "gaming_vol_gb": (monthly_gb * rng.uniform(0.01, 0.16, config.subscribers)).round(3),
        }
    )

    baseline_prb = np.clip(rng.normal(42, 10, config.cells), 15, 72)
    cells_table = pd.DataFrame(
        {
            "cell_id": cell_ids,
            "site_id": [site_for_cell[cell] for cell in cell_ids],
            "snapshot_month": snapshot,
            "avg_prb_utilisation_pct": np.clip(baseline_prb - rng.uniform(5, 12, config.cells), 5, 70).round(2),
            "p95_prb_utilisation_pct": baseline_prb.round(2),
            "max_prb_utilisation_pct": np.clip(baseline_prb + rng.uniform(2, 10, config.cells), 10, 85).round(2),
            "avg_dl_throughput_mbps": np.clip(rng.normal(55, 12, config.cells), 15, 120).round(2),
        }
    )

    dataset = {
        "crm_subscribers": crm,
        "usage_monthly": usage,
        "coverage_addresses": coverage,
        "service_consumption": service,
        "cell_kpis": cells_table,
    }
    if config.inject_anomalies:
        dataset["usage_monthly"].loc[0, "monthly_total_gb"] = np.nan
        dataset["usage_monthly"] = pd.concat([dataset["usage_monthly"], dataset["usage_monthly"].iloc[[0]]], ignore_index=True)
    return dataset


def validate_dataset(dataset: Dict[str, pd.DataFrame]) -> None:
    """Raise ValueError when required tables, keys, ranges, or joins are invalid."""
    required = {"crm_subscribers", "usage_monthly", "coverage_addresses", "service_consumption", "cell_kpis"}
    missing = required.difference(dataset)
    if missing:
        raise ValueError(f"Missing tables: {sorted(missing)}")

    crm = dataset["crm_subscribers"]
    usage = dataset["usage_monthly"]
    coverage = dataset["coverage_addresses"]
    services = dataset["service_consumption"]
    cells = dataset["cell_kpis"]
    if crm[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("CRM grain must be unique by subscriber and snapshot")
    if usage[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("Usage grain must be unique by subscriber and snapshot")
    if services[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("Service grain must be unique by subscriber and snapshot")
    if coverage["address_id"].duplicated().any() or cells["cell_id"].duplicated().any():
        raise ValueError("Coverage addresses and cells must have unique keys")
    if crm["subscriber_id"].nunique() != len(usage) or crm["subscriber_id"].nunique() != len(services):
        raise ValueError("Subscriber tables must have complete 1:1 coverage")
    if not set(usage["dominant_serving_cell_id"]).issubset(set(cells["cell_id"])):
        raise ValueError("Usage contains an unknown serving cell")
    if not set(coverage["serving_cell_id"]).issubset(set(cells["cell_id"])):
        raise ValueError("Coverage contains an unknown serving cell")
    if crm["arpu_monthly_tnd"].lt(0).any() or usage["monthly_total_gb"].lt(0).any():
        raise ValueError("Commercial and usage measures must be non-negative")
    if not cells["p95_prb_utilisation_pct"].between(0, 100).all():
        raise ValueError("PRB utilisation must be between 0 and 100")
    if dataset["coverage_addresses"][["latitude", "longitude"]].isna().any().any():
        raise ValueError("Coverage coordinates cannot be null")


def save_dataset(
    dataset: Dict[str, pd.DataFrame],
    output_dir: str | Path,
    config: SyntheticFwaConfig,
) -> dict:
    """Validate and save tables as Parquet files with a JSON run manifest."""
    validate_dataset(dataset)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for table_name, table in dataset.items():
        table.to_parquet(output_path / f"{table_name}.parquet", index=False)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "subscribers": config.subscribers,
            "cells": config.cells,
            "snapshot_month": config.snapshot_month,
            "seed": config.seed,
            "inject_anomalies": config.inject_anomalies,
        },
        "tables": {
            table_name: {"rows": len(table), "columns": list(table.columns)}
            for table_name, table in dataset.items()
        },
    }
    (output_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
