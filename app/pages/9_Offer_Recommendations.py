"""Page 9 — Offer Recommendations.

Step13 recommendation content: offer mix, tier-1 base plans, add-on split and
a masked, paginated recommendation table with drill-down to the subscriber
profile. ``offer_category = 'N/A'`` displays as "No Offer" (DECISION 2).
Reason codes are shown when present; otherwise the page states
"Recommendation explanation unavailable in the current dataset."
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
from app.business_logic import masking
from app.services import recommendation_service as reco
from app.state import session as S

st.set_page_config(page_title="Offer Recommendations", page_icon="9️⃣", layout="wide")

SNAPSHOT = "2026-01-01"
PAGE_SIZES = [25, 50, 100]


def main() -> None:
    S.init_session()
    S.page_default_population(S.POPULATION_ELIGIBLE)
    st.title("9 · Offer Recommendations")
    st.caption(
        "Recommendations from `step13` (verified pipeline output). Default: "
        "eligible. Subscriber IDs masked — open a row on Page 3 to drill down."
    )

    filters = F.render_global_filters()

    try:
        overview = reco.get_recommendation_overview(filters, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load recommendation overview: {exc}")
        return

    if overview["total"] == 0:
        M.render_empty_state("No recommendations for this selection.")
        return

    C.kpi_row(
        [
            {"label": "Subscribers (recommendations)", "value": f"{overview['total']:,}",
             "help": "Rows with a stored recommendation (step13)"},
            {"label": "With offer", "value": f"{overview['with_offer']:,}",
             "help": "offer_category != 'N/A'"},
            {"label": "No offer", "value": f"{overview['no_offer']:,}",
             "help": "offer_category = 'N/A' (displays as No Offer)"},
            {"label": "With reason codes", "value": f"{overview['with_reason']:,}",
             "help": "Rows whose reason_codes field is populated"},
        ],
        columns=4,
    )
    if overview["no_offer"]:
        M.render_warning(f"No Offer rows: {overview['no_offer']:,} — see the offer table below.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        offers = reco.get_offer_distribution(filters, SNAPSHOT)
        if not offers.empty:
            fig = C.donut_chart(offers["offer_category"].tolist(),
                                offers["count"].tolist(), title="Offer mix")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        plans = reco.get_tier1_distribution(filters, SNAPSHOT)
        if not plans.empty:
            fig = C.bar_chart(plans, x="plan_name", y="count", title="Tier-1 base plans")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Add-on distribution (tier-2 components)")
    addons = reco.get_addon_distribution(filters, SNAPSHOT)
    if not addons.empty:
        fig = C.bar_chart(addons, x="addons", y="count", title="Add-on bundles",
                          height=340)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Recommendation table (masked, paginated)")

    page_size = st.selectbox("Rows / page", PAGE_SIZES, index=1)
    if f"reco_page_size" not in st.session_state:
        st.session_state["reco_page_size"] = 50
    if st.session_state["reco_page_size"] != page_size:
        st.session_state["reco_page_size"] = page_size
        st.session_state["reco_page"] = 1
    page = st.session_state.get("reco_page", 1)

    try:
        data = reco.get_recommendation_page(filters, SNAPSHOT, page=page, page_size=page_size)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load recommendation rows: {exc}")
        return

    rows: pd.DataFrame = data["rows"]
    tbl = rows.copy()
    masking.mask_dataframe_identifiers(tbl)
    id_map = dict(zip(tbl["subscriber_id"], rows["subscriber_id"]))
    display = tbl[["subscriber_id", "fwa_suitability_score", "tier1_base_plan",
                   "tier2_addons", "recommended_offer", "offer_category",
                   "campaign_action", "churn_risk_band", "final_priority_score",
                   "reason_codes"]].copy()
    display["offer_category"] = display["offer_category"].replace("N/A", "No Offer")
    display["recommended_offer"] = display["recommended_offer"].fillna("—")
    display["reason_codes"] = display["reason_codes"].apply(
        lambda v: v if v not in (None, "", "[]", "none", "<NA>") else (
            "Recommendation explanation unavailable in the current dataset.")
    )

    st.dataframe(display, use_container_width=True, hide_index=True, height=440)

    n_pages = max(1, -(-data["total"] // page_size))
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Prev", disabled=page <= 1, use_container_width=True) and page > 1:
            st.session_state["reco_page"] = page - 1
            st.rerun()
    with c2:
        st.markdown(f"<p style='text-align:center'>Page {page} / {n_pages} — "
                    f"{data['total']:,} rows</p>", unsafe_allow_html=True)
    with c3:
        if st.button("Next ▶", disabled=page >= n_pages, use_container_width=True) and page < n_pages:
            st.session_state["reco_page"] = page + 1
            st.rerun()

    st.subheader("Drill down to subscriber profile")
    visible_ids = display["subscriber_id"].tolist()
    chosen_masked = st.selectbox("Choose a subscriber (masked ID)", visible_ids)
    if st.button("Open subscriber profile", use_container_width=True):
        S.select_subscriber(id_map[chosen_masked])
        st.switch_page("pages/3_Subscriber_Drill_Down.py")

    st.caption(
        "Rows without a stored reason code show the dataset-message above; "
        "explanations are not reconstructed client-side."
    )


if __name__ == "__main__":
    main()
