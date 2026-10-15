"""Page 3 — Subscriber Drill-Down.

Full masked profile for a subscriber: eligibility, churn, offers, capacity,
campaign action, verified explanation fields. Never shows msisdn; address
details aggregated to governorate.
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
from app.services import subscriber_service
from app.state import session as S

st.set_page_config(page_title="Subscriber Drill-Down", page_icon="3️⃣", layout="wide")


def main() -> None:
    S.init_session()
    S.page_default_population(S.POPULATION_ELIGIBLE)
    F.render_global_filters()
    st.title("3 · Subscriber Drill-Down")
    st.caption("Full masked profile. Source: step15 ⋈ abt ⋈ step13 ⋈ step14 (read-only).")

    selection = S.get_selection()
    subscriber_id = selection.get("subscriber_id")

    # --- search box ---
    term = st.text_input(
        "Search subscriber (masked ID or full ID)",
        value="",
        help="Type a masked/real subscriber ID prefix; choose from suggestions.",
    )
    if term:
        try:
            results = subscriber_service.search_subscribers(term, limit=15)
        except Exception as exc:  # noqa: BLE001
            M.render_error_state(f"Search failed: {exc}")
            results = pd.DataFrame()

        if results.empty:
            st.info("No subscriber matched that ID.")
        else:
            choices = results["subscriber_id_masked"].tolist()
            real_by_masked = dict(
                zip(results["subscriber_id_masked"], results["subscriber_id"])
            )
            chosen = st.selectbox("Select subscriber", choices)
            if st.button("Load profile"):
                S.select_subscriber(real_by_masked[chosen])
                st.rerun()

    if not subscriber_id:
        st.info("Select a subscriber on the Campaign Operations page (or search above) to see the profile.")
        return

    try:
        detail = subscriber_service.get_subscriber_details(subscriber_id, snapshot="2026-01-01")
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not load profile: {exc}")
        return

    if not detail["found"]:
        M.render_empty_state("Subscriber not found in the snapshot.")
        S.select_subscriber(None)
        return

    profile = detail["profile"].iloc[0]
    masked_id = masking.mask_subscriber_id(subscriber_id) or subscriber_id

    # --- header ---
    band = str(profile.get("fwa_suitability_band", "—"))
    st.subheader(f"🧑‍🔬 {masked_id}  ·  Band: {band}  ·  {profile.get('business_label', '—')}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Eligibility score", int(profile.get("fwa_suitability_score", 0)))
    col2.metric("Churn probability", f"{profile.get('churn_probability', 0):.3f}")
    col3.metric("Churn risk band", profile.get("churn_risk_band", "—"))
    col4.metric("Campaign action", profile.get("campaign_action", "—"))

    st.divider()

    # --- profile sections ---
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Eligibility & suitability**")
        _kv(profile, "fwa_suitability_score", "Suitability score")
        _kv(profile, "fwa_suitability_band", "Band")
        _kv(profile, "fwa_exclusion_reason", "Exclusion reason")
        _kv(profile, "radio_feasibility_class", "Radio feasibility")
        _kv(profile, "signal_quality_class", "Signal quality")
        _kv(profile, "rollout_status", "Rollout status")

        st.markdown("**Churn insight**")
        _kv(profile, "churn_probability", "Probability")
        _kv(profile, "churn_risk_band", "Risk band")

        st.markdown("**Recommendations**")
        _kv(profile, "recommended_offer", "Recommended offer")
        _kv(profile, "offer_category", "Offer category")
        _kv(profile, "tier1_base_plan", "Tier 1")
        _kv(profile, "tier2_addons", "Tier 2 add-ons")
        _kv(profile, "reason_codes", "Reason codes")

    with col_r:
        st.markdown("**Priority & campaign**")
        _kv(profile, "final_priority_score", "Final priority score")
        _kv(profile, "final_priority_band", "Priority band")
        _kv(profile, "campaign_action", "Action")
        _kv(profile, "post_migration_capacity_risk", "capacity risk (post migration)")

        st.markdown("**Network**")
        _kv(profile, "dominant_serving_cell_id", "Dominant cell")
        _kv(profile, "current_capacity_proxy_status", "Capacity status")
        _kv(profile, "governorate", "Governorate")

        st.markdown("**Behaviour & usage**")
        _kv(profile, "arpu_monthly_tnd", "ARPU (TND)")
        _kv(profile, "tenure_months", "Tenure (months)")
        _kv(profile, "num_active_lines", "Active lines")
        _kv(profile, "monthly_total_gb", "Monthly data (GB)")
        _kv(profile, "handset_5g_ready_flag", "5G-ready handset")
        _kv(profile, "streaming_heavy_flag", "Heavy streaming")
        _kv(profile, "gaming_heavy_flag", "Heavy gaming")
        _kv(profile, "high_voip_usage_flag", "High VoIP usage")

    # --- explanations ---
    st.divider()
    st.markdown("**Explanation of current recommendation**")
    reason = profile.get("fwa_exclusion_reason") or profile.get("reason_codes")
    if not reason or str(reason) in ("nan", "None"):
        st.write("Explanation unavailable in the current dataset.")
    else:
        st.write(str(reason))

    # --- export single row ---
    row_df = pd.DataFrame([profile.to_dict()])
    masked_row = masking.strip_and_mask_for_export(row_df)[0]
    st.download_button(
        "Export profile (masked CSV)",
        data=masked_row.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"profile_{masked_id.replace('…', '_')}.csv",
        mime="text/csv",
    )


def _kv(profile, key: str, label: str) -> None:
    val = D.display_value(key, profile.get(key))
    if pd.isna(val):
        val = "—"
    st.markdown(f"**{label}:** {val}")


if __name__ == "__main__":
    main()
