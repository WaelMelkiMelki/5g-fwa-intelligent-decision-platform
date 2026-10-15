"""Global filter bar — sidebar widgets bound to session state.

Implements interaction I1: user selection → session state → service query →
refreshed widgets. Filter options are loaded from the service layer (verified
distinct values), and a Reset button restores defaults.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from app.business_logic.filtering import (
    POPULATION_ALL,
    POPULATION_ELIGIBLE,
    POPULATION_EXCLUDED,
    POPULATION_KEY,
    POPULATION_VALUES,
)
from app.services.executive_service import get_filter_options
from app.state import session as S


def _label_map(key: str) -> str:
    return {
        "clusters": "Cluster / persona",
        "churn_bands": "Churn risk band",
        "coverage_classes": "Radio feasibility",
        "capacity_statuses": "Capacity status",
        "offers": "Offer category",
        "campaign_actions": "Campaign action",
    }[key]


def _cluster_label(value: Any) -> str:
    """Display alias for cluster sentinel -1 (DECISION 2); canonicals otherwise."""
    if value == -1:
        return "Not Segmented"
    return f"Cluster {value}"


def render_global_filters() -> Dict[str, Any]:
    """Render the master filter bar in the sidebar; returns active filter dict."""
    with st.sidebar:
        st.markdown("#### 🌐 Global filters")
        try:
            options = get_filter_options()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Unable to load filter options: {exc}")
            options = {}

        active = S.get_filters()
        selection = S.get_selection()
        new_filters: Dict[str, Any] = {}

        # snapshot month (single verified value 2026-01-01; future-proof)
        snapshots = options.get("snapshots") or ["2026-01-01"]
        chosen_snapshot = st.selectbox(
            "Snapshot month",
            options=snapshots,
            index=0,
            key="global_snapshot",
            help="Single snapshot in the current dataset (2026-01-01).",
        )

        # population scope (DECISION 2) — single-value select, not a column filter
        population = st.selectbox(
            "Population",
            options=POPULATION_VALUES,
            index=POPULATION_VALUES.index(active.get(POPULATION_KEY, POPULATION_ALL)),
            key="filter_population",
            on_change=S.mark_population_modified,
            help="All subscribers includes Excluded; segmentation/recommendation/"
            "capacity pages default to eligible.",
        )
        new_filters[POPULATION_KEY] = population

        for key in S.DEFAULT_FILTERS:
            if key == POPULATION_KEY:
                continue
            values = options.get(key, [])
            if key == "clusters":
                labels = {v: _cluster_label(v) for v in values}
            else:
                labels = {v: v for v in values}
            chosen = st.multiselect(
                _label_map(key),
                options=values,
                default=active.get(key, []),
                format_func=lambda v, m=labels: m.get(v, str(v)),
                key=f"filter_{key}",
                help=f"Filter by {_label_map(key)} (verified values).",
            )
            new_filters[key] = chosen

        S.set_filters(new_filters)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Reset filters", use_container_width=True):
                S.reset_filters()
                st.rerun()
        with col_b:
            if selection.get("cell_id") and st.button("Clear cell", use_container_width=True):
                S.select_cell(None)
                st.rerun()

        active_filter_count = sum(
            len(v) for k, v in new_filters.items() if k != POPULATION_KEY
        )
        if active_filter_count:
            st.caption(f"Active filters: {active_filter_count} value(s)")
        return S.get_filters()
