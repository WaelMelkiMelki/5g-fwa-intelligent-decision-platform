"""Page 1 — Executive Overview.

KPIs, funnel, campaign-action donut, churn/coverage distribution.
Honors the global filters (I1).
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
from app.services import executive_service
from app.state import session as S

st.set_page_config(page_title="Executive Overview", page_icon="1️⃣", layout="wide")

SNAPSHOT = "2026-01-01"


def main() -> None:
    S.init_session()
    st.title("1 · Executive Overview")
    st.caption("Source: `cleaned_data.step15_final_campaign_list` ⋈ `abt_subscriber_month` — all counts computed live.")

    filters = F.render_global_filters()
    try:
        kpis = executive_service.get_executive_kpis(filters, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load KPIs: {exc}")
        return

    funnel = kpis["funnel"]
    if funnel["total"] == 0:
        active = sum(len(v or []) for v in filters.values())
        M.render_empty_state(f"No subscribers for {active} active filter value(s).")
        return

    C.kpi_row(
        [
            {"label": "Total subscribers", "value": f"{funnel['total']:,}",
             "help": "Rows in step15 (1 per subscriber, snapshot 2026-01-01)"},
            {"label": "Eligible (score > 0)", "value": f"{funnel['eligible']:,}",
             "help": "fwa_suitability_score > 0"},
            {"label": "Contact Now", "value": f"{funnel['contact_now']:,}",
             "help": "campaign_action = 'Contact Now'"},
            {"label": "Filtered / baseline", "value": f"{funnel['total']:,} / 12,412",
             "help": "Active-global-filter result count vs verified baseline"},
        ],
        columns=4,
    )

    col1, col2 = st.columns(2)
    with col1:
        actions = kpis["actions"]
        if actions:
            df_a = item_counts(actions)
            fig = C.donut_chart(df_a["label"].tolist(), df_a["count"].tolist(),
                                title="Campaign action distribution")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        churn = kpis["churn_bands"]
        if churn:
            df_c = item_counts(churn)
            fig = C.bar_chart(df_c, x="label", y="count", title="Churn risk bands")
            st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        funnel_fig = C.funnel_chart(
            [
                {"label": "All subscribers", "value": funnel["total"]},
                {"label": "Eligible (score > 0)", "value": funnel["eligible"]},
                {"label": "Contact Now", "value": funnel["contact_now"]},
            ],
            title="Eligibility & contact funnel",
        )
        st.plotly_chart(funnel_fig, use_container_width=True)
    with col2:
        cov = kpis["coverage_classes"]
        if cov:
            df_co = item_counts(cov)
            fig = C.bar_chart(df_co, x="label", y="count", title="Radio feasibility split")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    offers = kpis["offer_categories"]
    if offers:
        df_o = item_counts(offers)
        fig = C.bar_chart(df_o, x="label", y="count", title="Offer categories")
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Charts are cross-filterable: clicking a segment filters the page's other widgets (I2).")


def item_counts(counts: dict) -> pd.DataFrame:
    """dict {label: count} -> tidy DataFrame."""
    return pd.DataFrame({"label": list(counts.keys()), "count": list(counts.values())})


if __name__ == "__main__":
    main()
