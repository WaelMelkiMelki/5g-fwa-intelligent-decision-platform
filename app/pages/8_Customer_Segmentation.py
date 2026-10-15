"""Page 8 — Customer Segmentation.

Persona intelligence from the precomputed clustering (step10 ->
``abt_subscriber_month_clustered``). The app never trains or re-runs
clustering and never invents labels: personas = the stored ``business_label``
values. ``cluster_id = -1`` displays as "Not Segmented".

Popup default: Eligible population (DECISION 2). Cluster selection
cross-filters the whole app via the global filters.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.components import charts as C
from app.components import filters as F
from app.components import messages as M
from app.services import segmentation_service as seg
from app.state import session as S

st.set_page_config(page_title="Customer Segmentation", page_icon="8️⃣", layout="wide")

SNAPSHOT = "2026-01-01"


def main() -> None:
    S.init_session()
    S.page_default_population(S.POPULATION_ELIGIBLE)
    st.title("8 · Customer Segmentation")
    st.caption(
        "Personas = stored precomputed clusters (step10), labelled directly "
        "from `business_label` — no labels invented here. Default: eligible."
    )

    filters = F.render_global_filters()

    try:
        summary = seg.get_cluster_summary(filters, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load segment summary: {exc}")
        return

    if summary.empty:
        M.render_empty_state("No segmented subscribers for this selection.")
        return

    mean_arpu = summary["mean_arpu"].mean()
    total = int(summary["subscribers"].sum())
    C.kpi_row(
        [
            {"label": "Segmented subscribers", "value": f"{total:,}",
             "help": "Rows with a precomputed cluster in the filtered data"},
            {"label": "Personas", "value": f"{len(summary):,}",
             "help": "Distinct stored business_label values"},
            {"label": "Mean ARPU (all)", "value": f"{mean_arpu:,.2f}",
             "help": "Simple mean over the current selection"},
            {"label": "Biggest persona", "value": summary.iloc[0]["business_label"],
             "help": "Persona with the largest size"},
        ],
        columns=4,
    )

    st.divider()
    fig = C.bar_chart(
        summary, x="cluster_id", y="subscribers", color="business_label",
        title="Persona sizes",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Persona profiles (means within each cluster)")
    st.dataframe(
        summary.rename(
            columns={
                "cluster_id": "Cluster",
                "business_label": "Persona",
                "subscribers": "Subscribers",
                "mean_arpu": "Mean ARPU",
                "mean_gb": "Mean GB/mo",
                "mean_streaming_gb": "Mean streaming GB",
                "mean_gaming_gb": "Mean gaming GB",
                "median_tenure": "Median tenure (mo)",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    st.divider()
    st.subheader("Cross-filter by cluster (applies the global cluster filter)")
    cluster_ids = sorted(summary["cluster_id"].dropna().unique().tolist())
    chosen = st.multiselect(
        "Clusters to focus",
        options=cluster_ids,
        format_func=lambda c: f"Cluster {c}",
    )
    if chosen != (filters.get("clusters") or []):
        S.update_filter("clusters", chosen)
        st.rerun()

    st.divider()
    st.subheader("Cross-tab: cluster × dimension")
    dimension = st.selectbox(
        "Dimension",
        options=list(seg.get_dimension_options().keys()),
        format_func=lambda k: seg.get_dimension_options()[k],
        index=0,
    )
    try:
        xt = seg.get_segment_cross_tab(filters, dimension, SNAPSHOT)
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load cross-tab: {exc}")
        return
    if xt.empty:
        M.render_empty_state("No cross-tab data for this selection.")
        return
    pivot = xt.set_index(dimension)
    fig = C.heatmap_chart(pivot.T, title=f"Cluster × {dimension}")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pivot, use_container_width=True, hide_index=False, height=320)


if __name__ == "__main__":
    main()
