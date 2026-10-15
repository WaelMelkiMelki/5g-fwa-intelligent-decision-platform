"""Page 10 — What-If Simulation.

Deterministic capacity & campaign-action scenarios over the eligible base.
All math is pure and in-memory (SIMULATION_CONTRACT.md); nothing is written
to the database and scenario results are never persisted. Defaults reproduce
the verified step14/step15 baseline exactly (identity property).

Controls: take rate, uplift cap, Safe/Waitlist PRB thresholds, and optional
per-category traffic-multiplier overrides.  Run → session state keeps
(params, result, stale, status); Reset reverts to idle.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.business_logic import masking, simulation
from app.components import charts as C
from app.components import filters as F
from app.components import messages as M
from app.services import simulation_service as sim
from app.state import session as S

st.set_page_config(page_title="What-If Simulation", page_icon="🔁", layout="wide")

SNAPSHOT = "2026-01-01"


def _current_param_form() -> dict:
    """Read the widget values into a param dict (values only, no run yet)."""
    return {
        "take_rate_pct": float(st.session_state.get("take_pct", 100.0)),
        "uplift_cap_pct": float(st.session_state.get("up_uplift_cap", 15.0)),
        "safe_threshold": float(st.session_state.get("safe_threshold", 80.0)),
        "waitlist_threshold": float(st.session_state.get("waitlist_threshold", 90.0)),
        "multiplier_overrides": {
            category: float(st.session_state.get(f"sim_mult_{category}", 0.0))
            for category in simulation.VERIFIED_OFFER_MULTIPLIERS
            if float(st.session_state.get(f"sim_mult_{category}", 0.0)) > 0
        },
    }


def main() -> None:
    S.init_session()
    st.title("10 · What-If Simulation")
    st.caption(
        "Deterministic scenario engine mirroring the verified step14/step15 "
        "formulas (see `SIMULATION_CONTRACT.md`). Read-only: no writes, no "
        "training, no persistence."
    )

    F.render_global_filters()

    with st.sidebar:
        st.markdown("#### 🔁 Scenario controls")

        def _on_change() -> None:
            S.mark_whatif_stale()

        st.number_input(
            "Take-up rate (%)", min_value=0.0, max_value=100.0, value=100.0,
            step=5.0, key="take_pct", on_change=_on_change,
            help="Share of eligible subscribers assumed to take the offer.",
        )
        st.number_input(
            "Uplift cap (%-points PRB)", min_value=0.0, max_value=30.0,
            value=15.0, step=1.0, key="up_uplift_cap", on_change=_on_change,
            help="Max. additional PRB proxy uplift per subscriber (step14 cap).",
        )
        st.number_input(
            "Safe threshold (% PRB)", min_value=40.0, max_value=95.0,
            value=80.0, step=5.0, key="safe_threshold", on_change=_on_change,
            help="Post-PRB above this marks the cell At Risk (verified).",
        )
        st.number_input(
            "Waitlist threshold (% PRB)", min_value=80.0, max_value=100.0,
            value=90.0, step=5.0, key="waitlist_threshold", on_change=_on_change,
            help="Post-PRB above this blocks the cell (verified).",
        )

        with st.expander("Per-category traffic multipliers (optional)"):
            for category, default_mult in simulation.VERIFIED_OFFER_MULTIPLIERS.items():
                st.number_input(
                    f"{category} (x demand)",
                    min_value=0.0, max_value=5.0, value=0.0, step=0.25,
                    key=f"sim_mult_{category}", on_change=_on_change,
                    help=f"Verified default: {default_mult}",
                )

        c1, c2 = st.columns(2)
        with c1:
            run_clicked = st.button("Run simulation", type="primary",
                                    use_container_width=True)
        with c2:
            reset_clicked = st.button("Reset", use_container_width=True)

    if reset_clicked:
        S.reset_whatif()
        st.rerun()

    if run_clicked:
        params = _current_param_form()
        try:
            result = sim.get_scenario_result(
                take_rate_pct=params["take_rate_pct"],
                multiplier_overrides=params["multiplier_overrides"],
                uplift_cap_pct=params["uplift_cap_pct"],
                safe_threshold=params["safe_threshold"],
                waitlist_threshold=params["waitlist_threshold"],
                snapshot=SNAPSHOT,
            )
            S.set_whatif_run(params, result, status="ok")
        except Exception as exc:  # noqa: BLE001
            S.set_whatif_error(f"Scenario failed: {exc}")
            M.render_error_state(f"Scenario failed: {exc}")
            return

    whatif = S.get_whatif()
    result = whatif["result"]

    st.caption(
        "⚠️ Scenario results are exploratory and are not persisted to "
        "operational campaign tables."
    )

    if result is None:
        st.info("Press **Run simulation** to compute a scenario.")
        return

    if whatif["stale"]:
        st.info("Parameters changed since the last run — press Run to refresh.")

    p = result["params"]
    C.kpi_row(
        [
            {"label": "Contact Now (scenario)",
             "value": f"{result['contact_now_scenario']:,}",
             "delta": f"{result['contact_now_scenario'] - result['contact_now_baseline']:+,} vs baseline",
             "help": "campaign_action = 'Contact Now' in the scenario"},
            {"label": "Changed actions",
             "value": f"{result['changed_actions']:,}",
             "help": "Subscribers whose action differs from step15 baseline"},
            {"label": "Cells at risk (scenario)",
             "value": f"{result['cells_at_risk_scenario']:,}",
             "delta": f"{result['cells_at_risk_scenario'] - result['cells_at_risk_baseline']:+,} vs baseline",
             "help": f"Cells with post-PRB > {p['safe_threshold']:.0f}%"},
            {"label": "Mean post-PRB (scenario)",
             "value": f"{result['mean_post_scenario']:.1f}%",
             "delta": f"{result['mean_post_scenario'] - result['mean_post_baseline']:+.1f} pp",
             "help": "Subscriber-weighted mean post-migration PRB proxy"},
        ],
        columns=4,
    )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        actions = result["actions"]
        if not actions.empty:
            fig = C.donut_chart(actions["campaign_action"].tolist(),
                                actions["count"].tolist(),
                                title="Scenario campaign actions")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        cells = result["cells"]
        st.metric("Scenario cells", f"{result['cells_total']:,}")
        st.dataframe(
            cells.rename(columns={
                "cell_id": "Cell",
                "subscribers": "Subs",
                "baseline_post": "PRB (baseline)",
                "scenario_post": "PRB (scenario)",
                "baseline_risk": "Risk (baseline)",
                "scenario_risk": "Risk (scenario)",
                "delta_post": "Δ PRB",
            }),
            use_container_width=True, hide_index=True, height=340,
        )

    st.divider()
    st.subheader("Action changes vs baseline (sample)")
    changed = result["changed"]
    if changed.empty:
        st.success("No action changes — scenario equals the baseline.")
    else:
        sample = changed[["subscriber_id", "campaign_action_baseline",
                          "campaign_action_scenario"]].head(20).copy()
        sample["subscriber_id"] = sample["subscriber_id"].map(masking.mask_subscriber_id)
        sample.columns = ["Subscriber (masked)", "Action (baseline)", "Action (scenario)"]
        st.dataframe(sample, use_container_width=True, hide_index=True, height=320)

    st.caption(
        "Identity property: defaults (take rate 100%, multipliers verified, "
        "caps/thresholds verified) reproduce the stored step14/step15 baseline."
    )


if __name__ == "__main__":
    main()
