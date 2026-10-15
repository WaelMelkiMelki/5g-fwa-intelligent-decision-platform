"""Page 4 — Network Capacity.

Cell-level KPIs: PRB p95 baseline, headroom-to-80%, capacity status,
subscriber counts, cell selection with subscriber mix, paginated cell table.
The cell map is shown only because the geographic join (cell ↔ address grid)
is verified; otherwise a clear explanation is displayed instead.
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
from app.services import capacity_service
from app.state import session as S

st.set_page_config(page_title="Network Capacity", page_icon="4️⃣", layout="wide")


def main() -> None:
    S.init_session()
    S.page_default_population(S.POPULATION_ELIGIBLE)
    F.render_global_filters()
    st.title("4 · Network Capacity")

    try:
        summary = capacity_service.get_capacity_summary()
        cells = capacity_service.get_all_cells()
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load capacity data: {exc}")
        return

    st.caption(
        f"Source: `t3_cell_monthly_kpi` ({summary['cells_total']:,} cells) ⋈ "
        "`step14_capacity_simulation` (eligible) · cell centroids from "
        "`t4_coverage_address_grid` (verified). Counts computed live."
    )

    constrained_count = int(
        (cells["current_capacity_proxy_status"] == "Constrained").sum()
        if not cells.empty
        else 0
    )
    if constrained_count == 0:
        st.info("No constrained cells exist in the current snapshot.")

    C.kpi_row(
        [
            {"label": "Cells", "value": f"{summary['cells_total']:,}",
             "help": "t3_cell_monthly_kpi rows (verified 731)"},
            {"label": "Cells at/over 80% PRB p95", "value": summary["at_prb_threshold"],
             "help": "verified 0 in current snapshot"},
            {"label": "Max PRB p95", "value": f"{summary['p95_max']:.2f}%"
             if summary["p95_max"] is not None else "—"},
            {"label": "Mean PRB p95", "value": f"{summary['p95_mean']:.2f}%"
             if summary["p95_mean"] is not None else "—"},
        ],
        columns=4,
    )

    col1, col2 = st.columns(2)
    with col1:
        if not cells.empty:
            st.plotly_chart(
                C.histogram_chart(
                    cells["p95_prb_utilisation_pct"],
                    nbins=40,
                    title="PRB p95 utilisation (%) — baseline",
                    vlines=[80.0],
                ),
                use_container_width=True,
            )
    with col2:
        if not cells.empty:
            st.plotly_chart(
                C.bar_chart(
                    cells.sort_values("p95_prb_utilisation_pct", ascending=False).head(20),
                    x="cell_id", y="p95_prb_utilisation_pct",
                    title="Top 20 cells by PRB p95",
                ),
                use_container_width=True,
            )

    # --- cell selection (I3) ---
    st.subheader("Select a cell")
    col1, col2 = st.columns([1, 2])
    with col1:
        options = cells["cell_id"].tolist() if not cells.empty else []
        selected = st.selectbox("Cell", options, help="Cell selection → KPIs + subscriber mix.")
    with col2:
        st.caption("Selected cell determines the panel below and drives the map tooltip.")

    if selected:
        S.select_cell(selected)
        _render_cell_panel(selected, cells)

    # --- paginated cell table ---
    st.subheader("Cell KPI table (paginated)")
    page_size = st.select_slider("Rows per page", [20, 50, 100], value=50)
    if "cap_page" not in st.session_state:
        st.session_state["cap_page"] = 1
    elif st.session_state.get("cap_page_size") != page_size:
        st.session_state["cap_page"] = 1
    st.session_state["cap_page_size"] = page_size

    try:
        table = capacity_service.get_cells_table(
            page=st.session_state["cap_page"],
            page_size=page_size,
            sort_column="p95_prb_utilisation_pct",
            sort_desc=True,
        )
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load cell table: {exc}")
        return

    rows = table["rows"].copy()
    rows["headroom_80"] = (80.0 - rows["p95_prb_utilisation_pct"]).clip(lower=0)
    st.dataframe(
        rows[
            ["cell_id", "site_id", "p95_prb_utilisation_pct", "max_prb_utilisation_pct",
             "headroom_80", "current_capacity_proxy_status", "subscriber_count"]
        ],
        use_container_width=True,
        hide_index=True,
        height=400,
    )
    n_pages = max(1, -(-table["total"] // page_size))
    b1, b2, b3 = st.columns([1, 3, 1])
    with b1:
        if st.button("◀ Prev", disabled=st.session_state["cap_page"] <= 1) and st.session_state["cap_page"] > 1:
            st.session_state["cap_page"] -= 1
            st.rerun()
    with b2:
        st.markdown(f"<p style='text-align:center'>Page {st.session_state['cap_page']} / {n_pages}</p>",
                    unsafe_allow_html=True)
    with b3:
        if st.button("Next ▶", disabled=st.session_state["cap_page"] >= n_pages) and st.session_state["cap_page"] < n_pages:
            st.session_state["cap_page"] += 1
            st.rerun()

    # --- map (verified geo join or clear explanation) ---
    st.subheader("Cell coverage map")
    _render_map(cells)


def _render_cell_panel(cell_id: str, cells: pd.DataFrame) -> None:
    try:
        row = cells[cells["cell_id"] == cell_id].iloc[0]
        count = capacity_service.get_cell_subscriber_count(cell_id)
        subs = capacity_service.get_cell_subscribers(cell_id, limit=10)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Cell {cell_id}: {exc}")
        return

    headroom = max(0.0, 80.0 - row["p95_prb_utilisation_pct"])
    st.markdown(f"**{cell_id}** — p95 {row['p95_prb_utilisation_pct']:.1f}% | "
                f"max {row['max_prb_utilisation_pct']:.1f}% | "
                f"status {row['current_capacity_proxy_status']} | "
                f"headroom-to-80 {headroom:.1f} pts | {count:,} eligible subscribers")
    if not subs.empty:
        st.dataframe(subs, use_container_width=True, hide_index=True, height=260)
    else:
        st.caption("No eligible subscribers mapped to this cell (step14 join).")


def _render_map(cells: pd.DataFrame) -> None:
    """Folium cell map from verified centroids; graceful fallback otherwise."""
    try:
        import folium
        from streamlit_folium import st_folium
    except ImportError:
        st.info(
            "Cell map unavailable: `folium` / `streamlit-folium` are not installed. "
            "Cell KPIs remain available in the table above."
        )
        return

    try:
        geo = capacity_service.get_cell_geo()
    except Exception:  # noqa: BLE001
        geo = pd.DataFrame()

    if geo.empty:
        st.info(
            "Map unavailable: no verified lat/lon join for the cell layer "
            "(`t4_coverage_address_grid` has no coordinates for this snapshot). "
            "KPIs remain available in the table above."
        )
        return

    merged = cells.merge(geo, on="cell_id", how="inner")
    if merged.empty:
        st.info("Map unavailable: geo join returned no cells for this snapshot.")
        return

    try:
        fmap = folium.Map(
            location=[merged["latitude"].mean(), merged["longitude"].mean()],
            zoom_start=9,
        )
        for _, row in merged.iterrows():
            color = "#2E9E44" if row["current_capacity_proxy_status"] == "Available" else "#C0392B"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4 + 3 * float(min(row["p95_prb_utilisation_pct"], 80.0)) / 80.0,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                tooltip=f"{row['cell_id']}: p95 {row['p95_prb_utilisation_pct']:.1f}%",
                popup=folium.Popup(
                    f"{row['cell_id']}<br/>p95 {row['p95_prb_utilisation_pct']:.1f}%<br/>"
                    f"max {row['max_prb_utilisation_pct']:.1f}%<br/>"
                    f"status {row['current_capacity_proxy_status']}",
                    max_width=250,
                ),
            ).add_to(fmap)
        st_folium(fmap, width="100%", height=420, returned_objects=[])
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Map rendering failed ({exc}) — table-only view is active.")


if __name__ == "__main__":
    main()
