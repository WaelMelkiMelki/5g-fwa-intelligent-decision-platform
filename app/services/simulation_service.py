"""What-If Simulation service — eligible snapshot loader + scenario runner.

The service is the DB-facing bridge for ``business_logic/simulation.py`:
it loads the eligible subscriber base (only the columns the engine needs) and
invokes the pure engine. All scenario math is computed in Python — the service
never writes to the database and never persists scenario results.

Formula sources: ``app/SIMULATION_CONTRACT.md`` (step14/step15 verified code).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from app.business_logic import guards, normalize, simulation
from app.services import database

SNAPSHOT = "2026-01-01"

LOADER_SQL = (
    "SELECT s.subscriber_id, "
    "       a.dominant_serving_cell_id, "
    "       s.offer_category, "
    "       a.monthly_total_gb, "
    "       a.avg_dl_throughput_mbps, "
    "       a.p95_prb_utilisation_pct, "
    "       s.fwa_suitability_score, "
    "       s.fwa_suitability_band, "
    "       s.churn_risk_band, "
    "       s.final_priority_score, "
    "       s.campaign_action "
    "FROM cleaned_data.step15_final_campaign_list s "
    "JOIN cleaned_data.abt_subscriber_month a "
    "ON a.subscriber_id = s.subscriber_id AND a.snapshot_month = s.snapshot_month "
    "WHERE s.snapshot_month = :snapshot AND s.fwa_suitability_score > 0 "
    "ORDER BY s.final_priority_score DESC NULLS LAST"
)


def load_eligible_base(snapshot: Optional[str] = None) -> pd.DataFrame:
    """Eligible subscriber base for simulation (single snapshot, read-only)."""
    guards.ensure_single_snapshot(database.run_query)
    df = database.run_query(
        LOADER_SQL, params={"snapshot": snapshot or SNAPSHOT}
    )
    return normalize.normalize_dataframe(df)


def get_scenario_result(
    take_rate_pct: float = 100.0,
    multiplier_overrides: Optional[Dict[str, float]] = None,
    uplift_cap_pct: float = simulation.PRB_UPLIFT_CAP_PCT,
    safe_threshold: float = simulation.SAFE_THRESHOLD,
    waitlist_threshold: float = simulation.WAITLIST_THRESHOLD,
    snapshot: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one deterministic scenario on the live eligible base."""
    df = load_eligible_base(snapshot)
    return simulation.run_simulation(
        df,
        take_rate_pct=take_rate_pct,
        multiplier_overrides=multiplier_overrides,
        uplift_cap_pct=uplift_cap_pct,
        safe_threshold=safe_threshold,
        waitlist_threshold=waitlist_threshold,
    )


def default_params() -> Dict[str, Any]:
    """Default scenario parameter set (page 10 initial state)."""
    return {
        "take_rate_pct": 100.0,
        "uplift_cap_pct": simulation.PRB_UPLIFT_CAP_PCT,
        "safe_threshold": simulation.SAFE_THRESHOLD,
        "waitlist_threshold": simulation.WAITLIST_THRESHOLD,
        "multiplier_overrides": {},
    }


def clean_multiplier_overrides(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Drop non-verified keys and coerce values to floats (None-safe)."""
    multipliers = (raw or {}).copy()
    cleaned: Dict[str, float] = {}
    for category, value in multipliers.items():
        if category in simulation.VERIFIED_OFFER_MULTIPLIERS:
            try:
                cleaned[category] = float(value)
            except (TypeError, ValueError):
                continue
    return cleaned
