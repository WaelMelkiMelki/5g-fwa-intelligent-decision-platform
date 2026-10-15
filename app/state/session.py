"""Session-state schema — single source of truth for the app's UI state.

Keys follow the interaction spec §9 pattern (``session.*`` prefix) but are
accessed via plain ``st.session_state`` keys implemented here:

- ``fwa.filters``        dict — active global filters
- ``fwa.selection``      dict — current entity selections (cell / subscriber / chart)
- ``fwa.ui``             dict — active page, loading, error flags

All writes go through typed helpers so keys stay consistent across pages.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

import streamlit as st

from app.business_logic.filtering import (
    POPULATION_ALL,
    POPULATION_ELIGIBLE,
    POPULATION_KEY,
)

SESSION_PREFIX = "fwa"

DEFAULT_FILTERS: Dict[str, Any] = {
    "clusters": [],                 # cluster_id values (incl. -1 for Excluded)
    "churn_bands": [],              # churn_risk_band values
    "coverage_classes": [],         # radio_feasibility_class
    "capacity_statuses": [],        # current_capacity_proxy_status
    "offers": [],                   # offer_category
    "campaign_actions": [],         # campaign_action
    POPULATION_KEY: POPULATION_ALL,  # population scope (single value, DECISION 2)
}

DEFAULT_SELECTION: Dict[str, Optional[Any]] = {
    "cell_id": None,
    "subscriber_id": None,
    "chart_selection": None,
}

# What-if simulation state (interaction spec §9 / §10; nothing is persisted).
DEFAULT_WHATIF: Dict[str, Any] = {
    "params": None,           # last RUN params (or None before first run)
    "result": None,           # last RUN result dict (or None)
    "stale": True,            # params changed since last run
    "status": "idle",         # idle | ok | error
    "last_error": None,
}


def _key(name: str) -> str:
    return f"{SESSION_PREFIX}.{name}"


def init_session() -> None:
    """Ensure all session keys exist with safe defaults (idempotent)."""
    if _key("filters") not in st.session_state:
        st.session_state[_key("filters")] = dict(DEFAULT_FILTERS)
    if _key("selection") not in st.session_state:
        st.session_state[_key("selection")] = dict(DEFAULT_SELECTION)
    if _key("ui") not in st.session_state:
        st.session_state[_key("ui")] = {
            "active_page": "overview",
            "loading": False,
            "error": None,
        }
    if _key("whatif") not in st.session_state:
        st.session_state[_key("whatif")] = dict(DEFAULT_WHATIF)


def get_filters() -> Dict[str, Any]:
    init_session()
    return st.session_state[_key("filters")]


def set_filters(new_filters: Dict[str, Any]) -> None:
    """Replace the whole filter dict (validated against allowed keys)."""
    allowed = set(DEFAULT_FILTERS)
    unknown = set(new_filters) - allowed
    if unknown:
        raise ValueError(f"Unknown filter keys: {sorted(unknown)}")
    clean = {k: (new_filters.get(k) or []) for k in DEFAULT_FILTERS}
    st.session_state[_key("filters")] = clean


def update_filter(key: str, values: List[Any]) -> None:
    """Update one filter dimension (empty list => no restriction)."""
    if key not in DEFAULT_FILTERS:
        raise ValueError(f"Unknown filter key: {key}")
    filters = get_filters()
    filters[key] = list(values)
    st.session_state[_key("filters")] = filters
    _bump_query_hash()


def get_population() -> str:
    """Current population scope (DECISION 2): All / Eligible / Excluded."""
    return str(get_filters().get(POPULATION_KEY, POPULATION_ALL))


def set_population(population: str) -> None:
    """Set the population scope and mark it as user-modified."""
    if population not in (POPULATION_ALL, POPULATION_ELIGIBLE):
        raise ValueError(f"Invalid population scope: {population!r}")
    filters = get_filters()
    filters[POPULATION_KEY] = population
    st.session_state[_key("filters")] = filters
    st.session_state[_key("population_touched")] = True
    _bump_query_hash()


def page_default_population(population: str) -> None:
    """Apply a page-level default population scope until the user changes it.

    Pages whose analyses are eligible-only by default (segmentation,
    recommendation, capacity — DECISION 2) call this before rendering their
    widgets so the DB selection defaults to the eligible pool.
    """
    if not st.session_state.get(_key("population_touched"), False):
        filters = get_filters()
        filters[POPULATION_KEY] = population
        st.session_state[_key("filters")] = filters
        _bump_query_hash()


def mark_population_modified() -> None:
    """Record that the user explicitly changed the population scope."""
    st.session_state[_key("population_touched")] = True


def reset_filters() -> None:
    """Reset all filters to unrestricted defaults."""
    st.session_state[_key("filters")] = dict(DEFAULT_FILTERS)
    reset_selection()
    _bump_query_hash()


def _bump_query_hash() -> None:
    filters = get_filters()
    token = str(sorted(filters.items()))
    st.session_state["query_hash"] = hashlib.sha256(token.encode()).hexdigest()[:10]


def get_selection() -> Dict[str, Optional[Any]]:
    init_session()
    return st.session_state[_key("selection")]


def select_cell(cell_id: Optional[str]) -> None:
    sel = get_selection()
    sel["cell_id"] = cell_id
    st.session_state[_key("selection")] = sel


def select_subscriber(subscriber_id: Optional[str]) -> None:
    sel = get_selection()
    sel["subscriber_id"] = subscriber_id
    st.session_state[_key("selection")] = sel


def set_chart_selection(payload: Optional[Any]) -> None:
    sel = get_selection()
    sel["chart_selection"] = payload
    st.session_state[_key("selection")] = sel


def get_ui() -> Dict[str, Any]:
    init_session()
    return st.session_state[_key("ui")]


def set_page(name: str) -> None:
    ui = get_ui()
    ui["active_page"] = name
    st.session_state[_key("ui")] = ui


def set_error(message: Optional[str]) -> None:
    ui = get_ui()
    ui["error"] = message
    st.session_state[_key("ui")] = ui


def is_any_filter_active() -> bool:
    filters = get_filters()
    return any(
        len(values or []) > 0
        for key, values in filters.items()
        if key != POPULATION_KEY
    )


def query_hash() -> str:
    """Hash of current filter state; used to key st.cache_data caches."""
    init_session()
    if "query_hash" not in st.session_state:
        _bump_query_hash()
    return str(st.session_state["query_hash"])


# --- What-if simulation state (page 10) -------------------------------------

def get_whatif() -> Dict[str, Any]:
    init_session()
    return st.session_state[_key("whatif")]


def set_whatif_run(params: Dict[str, Any], result: Any, status: str = "ok") -> None:
    """Store the most recent RUN (params + result), mark results current."""
    whatif = get_whatif()
    whatif["params"] = dict(params)
    whatif["result"] = result
    whatif["stale"] = False
    whatif["status"] = status
    whatif["last_error"] = None
    st.session_state[_key("whatif")] = whatif


def mark_whatif_stale() -> None:
    """Mark the stored result stale (parameters differ from last run)."""
    whatif = get_whatif()
    if whatif["params"] is not None:
        whatif["stale"] = True
        st.session_state[_key("whatif")] = whatif


def set_whatif_error(message: str) -> None:
    """Record a failed simulation run (no result change)."""
    whatif = get_whatif()
    whatif["status"] = "error"
    whatif["last_error"] = message
    whatif["stale"] = True
    st.session_state[_key("whatif")] = whatif


def reset_whatif() -> None:
    """Revert to baseline: clear stored params/result, mark idle."""
    st.session_state[_key("whatif")] = dict(DEFAULT_WHATIF)
