"""Explainable DuckDB eligibility and FWA suitability scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import duckdb
import pandas as pd


@dataclass(frozen=True)
class EligibilityConfig:
    """Business thresholds for the deterministic suitability policy."""

    base_score: int = 100
    no_5g_penalty: int = 20
    low_arpu_penalty: int = 15
    premium_minimum: int = 80
    standard_minimum: int = 60
    marginal_minimum: int = 40


REQUIRED_COLUMNS = {
    "subscriber_id",
    "snapshot_month",
    "current_capacity_proxy_status",
    "fiber_coverage_flag",
    "radio_feasibility_class",
    "coverage_5g_flag",
    "arpu_band",
}


def score_eligibility(
    abt: pd.DataFrame,
    config: EligibilityConfig | None = None,
) -> pd.DataFrame:
    """Apply the suitability policy to every ABT row using DuckDB SQL."""
    config = config or EligibilityConfig()
    missing = REQUIRED_COLUMNS.difference(abt.columns)
    if missing:
        raise ValueError(f"ABT is missing eligibility columns: {sorted(missing)}")
    if not 0 <= config.marginal_minimum <= config.standard_minimum <= config.premium_minimum <= config.base_score:
        raise ValueError("Eligibility score thresholds must be ordered within [0, base_score]")

    connection = duckdb.connect()
    try:
        connection.register("abt", abt)
        query = f"""
        WITH classified AS (
            SELECT
                subscriber_id,
                snapshot_month,
                CASE
                    WHEN fiber_coverage_flag THEN 'Fiber_Cannibalization'
                    WHEN radio_feasibility_class = 'Fiber_Competitor' THEN 'Fiber_Cannibalization'
                    WHEN radio_feasibility_class = 'Infeasible' THEN 'RF_Failure'
                    WHEN lower(current_capacity_proxy_status) = 'constrained' THEN 'Cell_Overload'
                    ELSE NULL
                END AS fwa_exclusion_reason,
                CASE
                    WHEN fiber_coverage_flag
                      OR radio_feasibility_class IN ('Fiber_Competitor', 'Infeasible')
                      OR lower(current_capacity_proxy_status) = 'constrained'
                    THEN 0
                    ELSE {config.base_score}
                        - CASE WHEN NOT coverage_5g_flag THEN {config.no_5g_penalty} ELSE 0 END
                        - CASE WHEN arpu_band IN ('Low ARPU', 'LV') THEN {config.low_arpu_penalty} ELSE 0 END
                END AS fwa_suitability_score
            FROM abt
        )
        SELECT
            subscriber_id,
            snapshot_month,
            fwa_suitability_score,
            CASE
                WHEN fwa_suitability_score >= {config.premium_minimum} THEN 'Premium'
                WHEN fwa_suitability_score >= {config.standard_minimum} THEN 'Standard'
                WHEN fwa_suitability_score >= {config.marginal_minimum} THEN 'Marginal'
                ELSE 'Excluded'
            END AS fwa_suitability_band,
            fwa_exclusion_reason
        FROM classified
        """
        return connection.execute(query).df()
    finally:
        connection.close()


def validate_eligibility(scores: pd.DataFrame) -> None:
    """Validate policy output and explainability invariants."""
    required = {
        "subscriber_id",
        "snapshot_month",
        "fwa_suitability_score",
        "fwa_suitability_band",
        "fwa_exclusion_reason",
    }
    missing = required.difference(scores.columns)
    if missing:
        raise ValueError(f"Eligibility output is missing columns: {sorted(missing)}")
    if scores[["subscriber_id", "snapshot_month"]].duplicated().any():
        raise ValueError("Eligibility output must be unique by subscriber and snapshot")
    if not scores["fwa_suitability_score"].between(0, 100).all():
        raise ValueError("Suitability scores must be between 0 and 100")
    excluded = scores["fwa_suitability_score"] == 0
    if scores.loc[excluded, "fwa_exclusion_reason"].isna().any():
        raise ValueError("Excluded rows must contain an exclusion reason")
    if scores.loc[~excluded, "fwa_exclusion_reason"].notna().any():
        raise ValueError("Eligible rows must not contain an exclusion reason")
    valid_bands = {"Premium", "Standard", "Marginal", "Excluded"}
    if not scores["fwa_suitability_band"].isin(valid_bands).all():
        raise ValueError("Eligibility output contains an invalid suitability band")
    if (scores.loc[excluded, "fwa_suitability_band"] != "Excluded").any():
        raise ValueError("Zero-score rows must be Excluded")


def save_eligibility(scores: pd.DataFrame, output_dir: str | Path) -> dict:
    """Validate and save eligibility scores plus a run manifest."""
    validate_eligibility(scores)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(output_path / "fwa_eligibility.parquet", index=False)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "table": "fwa_eligibility",
        "grain": ["subscriber_id", "snapshot_month"],
        "rows": len(scores),
        "columns": list(scores.columns),
    }
    (output_path / "eligibility_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
