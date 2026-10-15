"""Deterministic in-memory what-if engine — pure mirror of step14/step15 math.

This module contains NO database access and NO random processes: identical
inputs always produce identical outputs (unit-tested). It mirrors the verified
pipeline formulas:

Step 14 (`step14_post_migration_capacity_simulation.py`):
  T_req (Mbps)     = monthly_total_gb * (1024 * 8) / 2_592_000
  M_offer          = per-category verified multiplier (1.0 / 1.25 / 1.50);
                     overridable per category in the UI (baseline = verified map)
  uplift_full      = min(T_req * M_offer / avg_dl_throughput_mbps * 100, cap)
  uplift_scenario  = uplift_full * take_rate_pct / 100   (take rate scales demand)
  post_prb         = cell p95 + uplift_scenario
  risk / status    = post <= safe -> Safe/Approved; <= safe+10 -> High Risk/
                     Waitlist; else Blocked/Exclude (verified SAFE=80, WAIT=90)
  Zero/null cell throughput is imputed with the eligible-pool median (step14).

Step 15 (`step15_final_prioritization_campaign_action.py` §5) action gate, in
exact order Exclude -> Waitlist -> Manual Review -> Contact Now -> Contact Later:
  Exclude:       score == 0 OR post-risk == Blocked
  Waitlist:      post-risk == High Risk
  Manual Review: churn_risk_band in (High/Critical) AND band == Marginal
  Contact Now:   gated_priority >= eligible p75 AND post-risk == Safe

Identity property (tested against the live DB): take_rate=100%, no multiplier
overrides, cap 15%, safe=80, wait=90 reproduces step14_capacity_simulation and
step15_final_campaign_list exactly for the 2,923 eligible subscribers.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# Physics & engineering constants (verified in step14 script).
SECONDS_IN_30_DAYS = 30 * 24 * 3600  # 2,592,000
MB_TO_MBPS_FACTOR = (1024 * 8) / SECONDS_IN_30_DAYS
PRB_UPLIFT_CAP_PCT = 15.0
SAFE_THRESHOLD = 80.0
WAITLIST_THRESHOLD = 90.0
CONTACT_NOW_QUANTILE = 0.75  # step15: top-25% priority -> Contact Now

# Verified per-category traffic multiplier map (step14, line ~93).
VERIFIED_OFFER_MULTIPLIERS: dict = {
    "Base Only": 1.0,
    "Base + IPTV": 1.25,
    "Base + Gaming Add-on": 1.25,
    "Base + Convergent Fixed-Mobile Add-on": 1.25,
    "Multi-Addon Bundle": 1.50,
}

REQUIRED_COLUMNS = [
    "subscriber_id",
    "dominant_serving_cell_id",
    "offer_category",
    "monthly_total_gb",
    "avg_dl_throughput_mbps",
    "p95_prb_utilisation_pct",
    "fwa_suitability_score",
    "fwa_suitability_band",
    "churn_risk_band",
    "final_priority_score",
]


def effective_multipliers(overrides: Optional[dict] = None) -> dict:
    """Category multiplier map: verified defaults, optionally overridden."""
    merged = dict(VERIFIED_OFFER_MULTIPLIERS)
    for category, value in (overrides or {}).items():
        if category in merged:
            merged[category] = float(value)
    return merged


def validate_params(
    *,
    take_rate_pct: float,
    uplift_cap_pct: float,
    safe_threshold: float,
    waitlist_threshold: float,
) -> dict:
    """Clamp scenario parameters to their documented bounds (spec §10.2)."""
    take_rate = float(np.clip(take_rate_pct, 0.0, 100.0))
    uplift_cap = float(np.clip(uplift_cap_pct, 0.0, 30.0))
    safe = float(np.clip(safe_threshold, 40.0, 95.0))
    blocked = float(np.clip(waitlist_threshold, safe, 100.0))
    return {
        "take_rate_pct": take_rate,
        "uplift_cap_pct": uplift_cap,
        "safe_threshold": safe,
        "waitlist_threshold": blocked,
    }


def _impute_throughput(series: pd.Series) -> pd.Series:
    """Median-impute zero/null throughput (step14 lines 71-76)."""
    numeric = pd.to_numeric(series, errors="coerce")
    median = numeric.replace(0, np.nan).median()
    if pd.isna(median):
        return numeric.fillna(0.0)
    return numeric.replace(0, np.nan).fillna(median)


def _classify_post(post: pd.Series, safe: float, blocked: float) -> pd.DataFrame:
    """Step14 risk + rollout status from post-PRB (verified thresholds)."""
    risk = np.select(
        [
            post <= safe,
            (post > safe) & (post <= blocked),
            post > blocked,
        ],
        ["Safe", "High Risk", "Blocked"],
        default="Unknown",
    )
    status = np.where(
        risk == "Safe", "Approved",
        np.where(risk == "High Risk", "Waitlist", "Exclude"),
    )
    return pd.DataFrame(
        {
            "post_migration_capacity_risk": risk,
            "rollout_status": status,
        }
    )


def _gate_actions(
    df: pd.DataFrame, gated_priority: pd.Series, risk: pd.Series
) -> pd.Series:
    """Step15 action gate (priority order) over a gated-priority vector."""
    eligible = df["fwa_suitability_score"].fillna(0) > 0
    priority = pd.to_numeric(gated_priority, errors="coerce")
    eligible_priority = priority[eligible & priority.notna()]
    p75 = (
        eligible_priority.quantile(CONTACT_NOW_QUANTILE)
        if not eligible_priority.empty
        else np.inf
    )
    conditions = [
        (df["fwa_suitability_score"].fillna(0) == 0) | (risk == "Blocked"),
        risk == "High Risk",
        df["churn_risk_band"].isin(["High Risk", "Critical Risk"])
        & (df["fwa_suitability_band"] == "Marginal"),
        (priority >= p75) & (risk == "Safe"),
    ]
    return pd.Series(
        np.select(
            conditions,
            ["Exclude", "Waitlist", "Manual Review", "Contact Now"],
            default="Contact Later",
        ),
        index=df.index,
    )


def run_simulation(
    df: pd.DataFrame,
    *,
    take_rate_pct: float = 100.0,
    multiplier_overrides: Optional[dict] = None,
    uplift_cap_pct: float = PRB_UPLIFT_CAP_PCT,
    safe_threshold: float = SAFE_THRESHOLD,
    waitlist_threshold: float = WAITLIST_THRESHOLD,
) -> dict:
    """Run the deterministic capacity + campaign-action scenario.

    ``df`` is the eligible subscriber base (services/simulation_service.py).
    Identical inputs produce identical outputs (pure; unit-tested).

    Returns a dict with clamped params, per-subscriber frame, per-cell frame,
    action counts, baseline/scenario deltas and changed-action rows.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Simulation input missing columns: {missing}")
    params = validate_params(
        take_rate_pct=take_rate_pct,
        uplift_cap_pct=uplift_cap_pct,
        safe_threshold=safe_threshold,
        waitlist_threshold=waitlist_threshold,
    )
    multipliers = effective_multipliers(multiplier_overrides)

    empty_result = {
        "params": params,
        "contact_now_baseline": 0,
        "contact_now_scenario": 0,
        "changed_actions": 0,
        "cells_total": 0,
        "cells_at_risk_baseline": 0,
        "cells_at_risk_scenario": 0,
        "mean_post_baseline": None,
        "mean_post_scenario": None,
        "median_post_baseline": None,
        "median_post_scenario": None,
        "subscriber_rows": pd.DataFrame(),
        "cells": pd.DataFrame(),
        "actions": pd.DataFrame(columns=["campaign_action", "count"]),
        "changed": pd.DataFrame(),
    }
    if df.empty:
        return empty_result

    out = df.copy()
    out["T_req_mbps"] = (
        pd.to_numeric(out["monthly_total_gb"], errors="coerce") * MB_TO_MBPS_FACTOR
    )
    out["throughput_mbps"] = _impute_throughput(out["avg_dl_throughput_mbps"])
    out["M_offer"] = out["offer_category"].map(multipliers).fillna(1.0)

    # Full verified uplift (take = 100%) -> baseline; scenario scales it.
    out["expected_additional_prb_proxy_full"] = (
        out["T_req_mbps"]
        * out["M_offer"]
        / out["throughput_mbps"].replace(0, np.nan)
        * 100
    ).clip(upper=PRB_UPLIFT_CAP_PCT)
    out["post_prb_baseline"] = (
        pd.to_numeric(out["p95_prb_utilisation_pct"], errors="coerce")
        + out["expected_additional_prb_proxy_full"]
    )
    scenario_take = params["take_rate_pct"] / 100.0
    out["expected_additional_prb_proxy"] = (
        out["expected_additional_prb_proxy_full"] * scenario_take
    )
    out["post_prb_scenario"] = (
        pd.to_numeric(out["p95_prb_utilisation_pct"], errors="coerce")
        + out["expected_additional_prb_proxy"]
    )

    baseline_meta = _classify_post(
        out["post_prb_baseline"], params["safe_threshold"], params["waitlist_threshold"]
    )
    scenario_meta = _classify_post(
        out["post_prb_scenario"], params["safe_threshold"], params["waitlist_threshold"]
    )
    for col in ("post_migration_capacity_risk", "rollout_status"):
        out[f"{col}_baseline"] = baseline_meta[col].values
        out[col] = scenario_meta[col].values

    # Capacity gate (step15 §4): Blocked -> priority 0, then action gate.
    priority = pd.to_numeric(out["final_priority_score"], errors="coerce")
    out["gated_final_priority_score_baseline"] = priority.where(
        out["post_migration_capacity_risk_baseline"] != "Blocked", 0.0
    )
    out["gated_final_priority_score"] = priority.where(
        out["post_migration_capacity_risk"] != "Blocked", 0.0
    )
    out["campaign_action_baseline"] = _gate_actions(
        out,
        out["gated_final_priority_score_baseline"],
        out["post_migration_capacity_risk_baseline"],
    )
    out["campaign_action_scenario"] = _gate_actions(
        out, out["gated_final_priority_score"], out["post_migration_capacity_risk"]
    )

    # Prefer the DB baseline action when provided (step15 column).
    if "campaign_action" in df.columns:
        out["campaign_action_baseline"] = df["campaign_action"].values

    changed = out.loc[
        out["campaign_action_scenario"].ne(out["campaign_action_baseline"])
    ].copy()
    actions = (
        out["campaign_action_scenario"]
        .value_counts()
        .rename_axis("campaign_action")
        .reset_index(name="count")
    )

    cells = (
        out.groupby("dominant_serving_cell_id")
        .agg(
            subscribers=("subscriber_id", "count"),
            baseline_post=("post_prb_baseline", "max"),
            scenario_post=("post_prb_scenario", "max"),
        )
        .reset_index()
        .rename(columns={"dominant_serving_cell_id": "cell_id"})
    )
    cells["baseline_risk"] = np.where(
        cells["baseline_post"] > params["safe_threshold"], "At Risk", "Safe"
    )
    cells["scenario_risk"] = np.where(
        cells["scenario_post"] > params["safe_threshold"], "At Risk", "Safe"
    )
    cells["delta_post"] = (cells["scenario_post"] - cells["baseline_post"]).round(3)
    cells = cells.sort_values("scenario_post", ascending=False).reset_index(drop=True)

    return {
        "params": params,
        "contact_now_baseline": int(
            (out["campaign_action_baseline"] == "Contact Now").sum()
        ),
        "contact_now_scenario": int(
            (out["campaign_action_scenario"] == "Contact Now").sum()
        ),
        "changed_actions": int(len(changed)),
        "subs_blocked_scenario": int((out["post_migration_capacity_risk"] == "Blocked").sum()),
        "subs_waitlist_scenario": int((out["post_migration_capacity_risk"] == "High Risk").sum()),
        "cells_total": int(len(cells)),
        "cells_at_risk_baseline": int((cells["baseline_risk"] == "At Risk").sum()),
        "cells_at_risk_scenario": int((cells["scenario_risk"] == "At Risk").sum()),
        "mean_post_baseline": float(out["post_prb_baseline"].mean()),
        "mean_post_scenario": float(out["post_prb_scenario"].mean()),
        "median_post_baseline": float(out["post_prb_baseline"].median()),
        "median_post_scenario": float(out["post_prb_scenario"].median()),
        "subscriber_rows": out,
        "cells": cells,
        "actions": actions,
        "changed": changed,
    }


def parse_params(**kwargs) -> dict:
    """Public param validation (used by the WHAT-IF page and tests)."""
    return validate_params(**kwargs)
