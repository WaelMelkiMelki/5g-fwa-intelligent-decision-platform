"""Data-quality checks for the public synthetic source tables and ABT."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import pandas as pd

from .abt import SOURCE_TABLES


def _check(name: str, passed: bool, details: str) -> dict[str, object]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "details": details}


def run_quality_checks(
    dataset: Mapping[str, pd.DataFrame],
    abt: pd.DataFrame,
) -> dict[str, object]:
    """Return a JSON-serializable quality report for source tables and ABT."""
    checks: list[dict[str, object]] = []
    missing = set(SOURCE_TABLES).difference(dataset)
    checks.append(_check("required_source_tables", not missing, f"missing={sorted(missing)}"))

    for table_name in SOURCE_TABLES:
        if table_name not in dataset:
            continue
        table = dataset[table_name]
        checks.append(_check(f"{table_name}_non_empty", len(table) > 0, f"rows={len(table)}"))

    grain_specs = {
        "crm_subscribers": ["subscriber_id", "snapshot_month"],
        "usage_monthly": ["subscriber_id", "snapshot_month"],
        "service_consumption": ["subscriber_id", "snapshot_month"],
        "coverage_addresses": ["address_id"],
        "cell_kpis": ["cell_id", "snapshot_month"],
        "abt_subscriber_month": ["subscriber_id", "snapshot_month"],
    }
    for table_name, keys in grain_specs.items():
        table = abt if table_name == "abt_subscriber_month" else dataset.get(table_name)
        if table is None:
            continue
        duplicates = int(table.duplicated(keys).sum())
        checks.append(_check(f"{table_name}_grain_unique", duplicates == 0, f"duplicate_rows={duplicates}"))
        null_keys = int(table[keys].isna().any(axis=1).sum())
        checks.append(_check(f"{table_name}_keys_not_null", null_keys == 0, f"rows_with_null_keys={null_keys}"))

    snapshot_tables = [
        table_name
        for table_name in SOURCE_TABLES
        if "snapshot_month" in dataset[table_name].columns
    ]
    snapshots = {
        str(pd.Timestamp(value).date())
        for table_name in snapshot_tables
        for value in dataset[table_name]["snapshot_month"].dropna().unique()
    }
    abt_snapshots = {str(pd.Timestamp(value).date()) for value in abt["snapshot_month"].dropna().unique()}
    checks.append(_check("source_single_snapshot", len(snapshots) == 1, f"snapshots={sorted(snapshots)}"))
    checks.append(_check("abt_single_snapshot", len(abt_snapshots) == 1, f"snapshots={sorted(abt_snapshots)}"))
    checks.append(_check("source_abt_snapshot_match", snapshots == abt_snapshots, f"source={sorted(snapshots)} abt={sorted(abt_snapshots)}"))

    crm = dataset["crm_subscribers"]
    usage = dataset["usage_monthly"]
    coverage = dataset["coverage_addresses"]
    services = dataset["service_consumption"]
    cells = dataset["cell_kpis"]
    checks.extend(
        [
            _check("usage_subscriber_keys_match", set(usage["subscriber_id"]) == set(crm["subscriber_id"]), "usage versus CRM subscribers"),
            _check("service_subscriber_keys_match", set(services["subscriber_id"]) == set(crm["subscriber_id"]), "services versus CRM subscribers"),
            _check("coverage_address_keys_match", set(coverage["address_id"]) == set(crm["address_id"]), "coverage versus CRM addresses"),
            _check("usage_cells_exist", set(usage["dominant_serving_cell_id"]).issubset(set(cells["cell_id"])), "usage serving cells versus KPI cells"),
            _check("coverage_cells_exist", set(coverage["serving_cell_id"]).issubset(set(cells["cell_id"])), "coverage serving cells versus KPI cells"),
            _check("abt_row_count_matches_crm", len(abt) == len(crm), f"abt={len(abt)} crm={len(crm)}"),
            _check("arpu_non_negative", bool(crm["arpu_monthly_tnd"].ge(0).all()), "CRM ARPU range"),
            _check("traffic_non_negative", bool(usage["monthly_total_gb"].ge(0).all()), "monthly traffic range"),
            _check("prb_range_valid", bool(cells["p95_prb_utilisation_pct"].between(0, 100).all()), "cell P95 PRB range"),
            _check("abt_prb_range_valid", bool(abt["p95_prb_utilisation_pct"].between(0, 100).all()), "ABT P95 PRB range"),
        ]
    )

    failed = [check for check in checks if check["status"] == "FAIL"]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "status": "PASS" if not failed else "FAIL",
        },
        "tables": {name: {"rows": len(table), "columns": list(table.columns)} for name, table in dataset.items()},
        "abt": {"rows": len(abt), "columns": list(abt.columns)},
        "checks": checks,
    }


def save_quality_report(report: dict[str, object], output_path: str | Path) -> None:
    """Persist a quality report as formatted JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
