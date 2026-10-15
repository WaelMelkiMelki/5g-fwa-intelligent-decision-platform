"""Pure metric computations over unfiltered/filtered DataFrames.

These functions are deterministic, side-effect free, and unit-testable without
a database. Page-layer computations (funnels, distributions, capacity
headroom) delegate here.

All numbers are derived from live query results; nothing is hard-coded.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


def funnel_rows(df: pd.DataFrame, score_col: str = "fwa_suitability_score") -> Dict[str, int]:
    """Compute the executive funnel: total, eligible (score>0), contact-now count.

    Returns counts only for the rows present in ``df`` (already filtered).
    """
    total = int(len(df))
    eligible = int((df[score_col] > 0).sum()) if score_col in df.columns else 0
    contact_now = (
        int((df["campaign_action"] == "Contact Now").sum())
        if "campaign_action" in df.columns
        else 0
    )
    return {"total": total, "eligible": eligible, "contact_now": contact_now}


def value_counts_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Safe count by value with NaN handled (excluded values keep their label)."""
    if column not in df.columns:
        return pd.Series(dtype=int)
    return df[column].fillna("(None)").value_counts().sort_index()


def churn_band_counts(df: pd.DataFrame) -> pd.Series:
    return value_counts_series(df, "churn_risk_band")


def action_counts(df: pd.DataFrame) -> pd.Series:
    return value_counts_series(df, "campaign_action")


def exclusion_reason_counts(df: pd.DataFrame) -> pd.Series:
    return value_counts_series(df, "fwa_exclusion_reason")


def capacity_headroom(df_cells: pd.DataFrame, threshold: float = 80.0) -> Dict[str, Any]:
    """Capacity metrics from a cell-KPI dataframe (p95 vs threshold).

    Returns KPIs: count cells, cells at/over threshold, max p95, headroom stats.
    """
    empty = {
        "cells": 0,
        "cells_at_or_over": 0,
        "max_p95": None,
        "pct_at_or_over": 0.0,
        "mean_headroom": None,
    }
    if df_cells is None or df_cells.empty or "p95_prb_utilisation_pct" not in df_cells.columns:
        return empty
    p95 = df_cells["p95_prb_utilisation_pct"]
    at_or_over = int((p95 >= threshold).sum())
    return {
        "cells": int(len(df_cells)),
        "cells_at_or_over": at_or_over,
        "max_p95": float(p95.max()),
        "pct_at_or_over": round(100.0 * at_or_over / max(1, len(df_cells)), 2),
        "mean_headroom": float((threshold - p95).clip(lower=0).mean()),
    }


def safe_percentage(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def pivot_table(df: pd.DataFrame, index: str, column: str) -> pd.DataFrame:
    """Cross-tab (rows=index values, cols=column values) as a plain DataFrame."""
    if index not in df.columns or column not in df.columns:
        return pd.DataFrame()
    return (
        df.fillna({index: "(None)", column: "(None)"})
        .groupby([index, column])
        .size()
        .unstack(fill_value=0)
    )
