"""Page 2 — Campaign Operations.

Searchable, filterable, sortable, paginated campaign table + masked CSV export.
Subscriber row selection keeps the real ID only in the selection state (never
rendered); the visible table and all exports are masked (I4/I6).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from app.business_logic import display as D
from app.business_logic import masking
from app.components import filters as F
from app.components import messages as M
from app.services import campaign_service
from app.state import session as S

st.set_page_config(page_title="Campaign Operations", page_icon="2️⃣", layout="wide")

SNAPSHOT = "2026-01-01"

SORT_OPTIONS = {
    "final_priority_score": "Final priority score",
    "fwa_suitability_score": "Suitability score",
    "churn_probability": "Churn probability",
    "arpu_monthly_tnd": "ARPU (TND)",
    "tenure_months": "Tenure (months)",
    "num_active_lines": "Active lines",
    "candidate_prioritization_score": "MCDA score",
}
PAGE_SIZES = [50, 100, 200]


def main() -> None:
    S.init_session()
    st.title("2 · Campaign Operations")
    st.caption(
        "Search, filter, sort, paginate · subscriber IDs masked in view and export · "
        "select a row for drill-down on Page 3."
    )

    filters = F.render_global_filters()

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        search = st.text_input(
            "Search (masked subscriber ID)",
            placeholder="e.g. SUB_A220",
            help="Partial masked-ID search (applied in-memory on the current page).",
        )
    with c2:
        sort_col = st.selectbox(
            "Sort by", list(SORT_OPTIONS.keys()),
            format_func=lambda k: SORT_OPTIONS[k], index=0,
        )
    with c3:
        sort_desc = st.checkbox("Descending", value=True)
    with c4:
        page_size = st.selectbox("Rows / page", PAGE_SIZES, index=0)

    if "campaign_page" not in st.session_state:
        st.session_state["campaign_page"] = 1
    if "campaign_page_size" not in st.session_state:
        st.session_state["campaign_page_size"] = 50
    if st.session_state["campaign_page_size"] != page_size:
        st.session_state["campaign_page"] = 1
        st.session_state["campaign_page_size"] = page_size

    page = st.session_state["campaign_page"]

    try:
        data = campaign_service.get_subscribers(
            filters,
            page=page,
            page_size=page_size,
            sort_column=sort_col,
            sort_desc=sort_desc,
            snapshot=SNAPSHOT,
        )
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load campaign list: {exc}")
        return

    rows: pd.DataFrame = data["rows"]
    total = data["total"]

    st.metric("Rows matching filters", f"{total:,}")

    if search.strip():
        pattern = search.strip().lower()
        rows = rows[
            rows["subscriber_id"].astype(str).str.lower().str.contains(pattern, na=False)
        ]

    if total == 0:
        M.render_empty_state("No subscribers match the current filters.")
        return
    if rows.empty:
        M.render_empty_state("No subscribers match the current search.")
        return

    tbl = rows.copy()
    masking.mask_dataframe_identifiers(tbl)
    tbl = D.apply_sentinel_labels(tbl)

    # keep real id mapping (never rendered)
    id_map = dict(zip(tbl["subscriber_id"], rows["subscriber_id"]))

    st.dataframe(tbl, use_container_width=True, hide_index=True, height=420)

    # ---- pagination ----
    n_pages = max(1, -(-total // page_size))
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Previous", disabled=page <= 1, use_container_width=True) and page > 1:
            st.session_state["campaign_page"] = page - 1
            st.rerun()
    with c2:
        st.markdown(f"<p style='text-align:center'>{page} / {n_pages}</p>", unsafe_allow_html=True)
    with c3:
        if st.button("Next ▶", disabled=page >= n_pages, use_container_width=True) and page < n_pages:
            st.session_state["campaign_page"] = page + 1
            st.rerun()

    # ---- drill-down ----
    st.subheader("Drill down")
    visible_ids = tbl["subscriber_id"].tolist()
    chosen_masked = st.selectbox("Choose a subscriber", visible_ids)
    if st.button("Open drill-down for this subscriber", use_container_width=True):
        S.select_subscriber(id_map[chosen_masked])  # real id stored in state only
        st.switch_page("pages/3_Subscriber_Drill_Down.py")

    # ---- export ----
    st.subheader("Export (I6)")
    st.caption(
        "Exports the **entire filtered population** (server-side, all pages, "
        "not just the visible page) with masked IDs and no sensitive columns."
    )
    try:
        bytes_data, filename, count = campaign_service.export_csv_bytes(
            filters, SNAPSHOT, page_slug="campaign"
        )
        st.download_button(
            "Download CSV (masked, UTF-8 BOM)",
            data=bytes_data,
            file_name=filename,
            mime="text/csv",
            disabled=count == 0,
        )
        st.caption(f"{count:,} rows · filename per spec I6 · no msisdn exported.")
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Export unavailable: {exc}")


if __name__ == "__main__":
    main()
