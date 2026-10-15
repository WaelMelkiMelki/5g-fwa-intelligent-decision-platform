"""Page 7 — Coverage & Eligibility.

Coverage feasibility, suitability bands, exclusion reasons and cell-level
capacity risk. The geo map shows ONLY privacy-safe cell centroids (aggregate
of the address grid) — never subscriber coordinates. The map renders only
when the subscriber→address-grid join is verified (12,412/12,412).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from app.components import charts as C
from app.components import filters as F
from app.components import messages as M
from app.services import coverage_service as cov
from app.state import session as S

st.set_page_config(page_title="Coverage & Eligibility", page_icon="7️⃣", layout="wide")

SNAPSHOT = "2026-01-01"

FOCUS_OPTIONS = ["(All classes)", "5G_Feasible", "4G_Fallback", "Infeasible", "Fiber_Competitor"]


def main() -> None:
    S.init_session()
    st.title("7 · Coverage & Eligibility")
    st.caption(
        "Eligibility = fwa_suitability_score > 0. All counts computed live "
        "from `step15` ⋈ `abt_subscriber_month` (+ address grid)."
    )

    filters = F.render_global_filters()

    focus = st.selectbox("Coverage class focus", FOCUS_OPTIONS, index=0,
                         help="Re-centres the distributions and cell table on one class.")
    focus_filters = dict(filters)
    if focus != FOCUS_OPTIONS[0]:
        focus_filters["coverage_classes"] = [focus]

    try:
        kpis = cov.get_coverage_kpis(focus_filters, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load coverage KPIs: {exc}")
        return

    total = kpis["total"]
    if total == 0:
        M.render_empty_state("No subscribers match the current filters.")
        return

    C.kpi_row(
        [
            {"label": "Subscribers", "value": f"{total:,}",
             "help": "Rows in the filtered base population"},
            {"label": "Eligible (score > 0)", "value": f"{kpis['eligible']:,}",
             "help": "fwa_suitability_score > 0"},
            {"label": "Excluded", "value": f"{kpis['excluded']:,}",
             "help": "fwa_suitability_score <= 0"},
            {"label": "Feasibility classes", "value": f"{len(kpis['coverage_classes']):,}",
             "help": "Verified classes present in filtered data"},
        ],
        columns=4,
    )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        cov_cls = kpis["coverage_classes"]
        fig = C.donut_chart(list(cov_cls.keys()), list(cov_cls.values()),
                            title="Radio feasibility split")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        sig = kpis["signal_quality"]
        if sig:
            fig = C.bar_chart(_items(sig), x="label", y="count",
                              title="Signal quality classes")
            st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        suit = cov.get_suitability_distribution(focus_filters, SNAPSHOT)
        if not suit.empty:
            fig = C.bar_chart(suit, x="band", y="count", title="Suitability bands")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        reasons = cov.get_exclusion_reasons(focus_filters, SNAPSHOT)
        if not reasons.empty:
            fig = C.bar_chart(reasons, x="reason", y="count", title="Exclusion reasons")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Cell capacity risk (by dominant serving cell)")
    try:
        cells = cov.get_cell_risk_table(focus_filters, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load cell table: {exc}")
        return
    if cells.empty:
        M.render_empty_state("No cell-level data for this selection.")
        return

    eligible_cells = st.selectbox(
        "Focus a cell (updates the cell selection used across pages)",
        options=["(none)"] + cells["cell_id"].astype(str).tolist(),
        index=0,
    )
    if eligible_cells != "(none)":
        S.select_cell(str(eligible_cells))

    st.dataframe(cells, use_container_width=True, hide_index=True, height=420)

    st.divider()
    st.subheader("Coverage map (privacy-safe cell centroids)")
    gate = cov.is_geo_join_verified()
    if not gate["verified"]:
        M.render_warning(
            "Coverage map unavailable because the geographic join or "
            "privacy-safe grain has not been verified."
        )
    else:
        centroids = cov.get_cell_centroid_overlay()
        if centroids.empty:
            M.render_empty_state("No cell centroids available.")
        else:
            st.map(centroids[["lat", "lon"]], use_container_width=True)
        grid = cov.get_grid_summary()
        C.kpi_row(
            [
                {"label": "Address points", "value": f"{grid['points']:,}",
                 "help": "t4_coverage_address_grid rows"},
                {"label": "Serving cells", "value": f"{grid['cells']:,}",
                 "help": "Distinct serving_cell_id in the grid"},
                {"label": "Governorates", "value": f"{grid['governorates']:,}",
                 "help": "Distinct governorates covered"},
                {"label": "Map grain", "value": "cell-level",
                 "help": "Centroids are aggregated; no subscriber coordinates"},
            ],
            columns=4,
        )


def _items(counts: dict) -> pd.DataFrame:
    return pd.DataFrame({"label": list(counts.keys()), "count": list(counts.values())})


if __name__ == "__main__":
    main()
