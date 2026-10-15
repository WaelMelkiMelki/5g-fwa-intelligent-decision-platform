"""Message / status components — banners, empty and error states, drift alert."""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

VERIFIED_BASELINES = {
    "abt_subscriber_month": 12412,
    "step15_final_campaign_list": 12412,
    "t3_cell_monthly_kpi": 731,
}


def render_drift_banner(counts: Optional[Dict[str, int]] = None) -> bool:
    """Render an amber drift banner when live counts differ from verified
    baselines (I8). Returns True when drift detected."""
    drift = []
    for table, expected in VERIFIED_BASELINES.items():
        actual = (counts or {}).get(table)
        if actual is not None and actual != expected:
            drift.append(f"{table}: {actual} vs expected {expected}")
    if drift:
        st.warning("⚠️ **Snapshot drift detected** — " + "; ".join(drift))
        return True
    return False


def render_empty_state(message: str = "No data for this selection.") -> None:
    st.info(f"📭 {message}")
    if st.button("Reset filters", key="empty_reset"):
        from app.state import session as S

        S.reset_filters()
        st.rerun()


def render_error_state(message: str) -> None:
    st.error(f"🚨 {message}")
    if st.button("Retry", key="retry_btn"):
        st.cache_data.clear()
        st.rerun()


def render_warning(message: str) -> None:
    """Amber warning banner (e.g. metric-validation-required notice)."""
    st.warning(message)


def render_source_note(source: str) -> None:
    st.caption(f"Source: {source}")
