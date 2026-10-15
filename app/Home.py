"""5G FWA Decision-Support Dashboard — Phase 1 (read-only MVP).

Entry point: ``streamlit run Home.py`` (from inside app/).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit adds this script's directory (app/) to sys.path; the `app` package
# lives in the project root, so add it explicitly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.components import filters as F
from app.components import messages
from app.services import database
from app.state import session as S

st.set_page_config(
    page_title="5G FWA Decision Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    S.init_session()
    F.render_global_filters()
    st.title("📡 5G FWA Decision-Support Dashboard")
    st.caption(
        "Read-only MVP — data source: PostgreSQL `cleaned_data` (snapshot 2026-01-01). "
        "PII masked. No writes to the database."
    )

    with st.spinner("Checking data freshness…"):
        try:
            counts = database.run_query(
                """
                SELECT
                  (SELECT COUNT(*) FROM cleaned_data.step15_final_campaign_list) AS campaign,
                  (SELECT COUNT(*) FROM cleaned_data.abt_subscriber_month)        AS abt,
                  (SELECT COUNT(*) FROM cleaned_data.t3_cell_monthly_kpi)         AS cells
                """
            ).iloc[0]
            actual = {
                "step15_final_campaign_list": int(counts["campaign"]),
                "abt_subscriber_month": int(counts["abt"]),
                "t3_cell_monthly_kpi": int(counts["cells"]),
            }
            messages.render_drift_banner(actual)
            st.success(
                f"Connected. Snapshot 2026-01-01 · "
                f"{actual['abt_subscriber_month']:,} subscribers · "
                f"{actual['t3_cell_monthly_kpi']:,} cells · "
                f"{actual['step15_final_campaign_list']:,} campaign rows."
            )
        except database.DatabaseConfigError as exc:
            st.error(f"Configuration problem: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Unable to reach the database: {exc}")

    st.divider()
    st.markdown(
        """
        ### Pages
        Use the left navigation (or the page links below) to explore:

        | Page | Purpose |
        |---|---|
        | **1 · Executive Overview** | Funnel, campaign actions, churn & coverage distribution |
        | **2 · Campaign Operations** | Searchable, filterable, paginated campaign list + export |
        | **3 · Subscriber Drill-Down** | Full masked profile for a subscriber |
        | **4 · Network Capacity** | Cell KPIs, PRB p95, headroom, cell selection |
        | **5 · Model Performance** | Verified precomputed model metrics (conflicts flagged) |
        | **6 · Data Quality** | Aggregate validation of snapshot baselines (PASS/WARN/FAIL) |
        | **7 · Coverage & Eligibility** | Feasibility, suitability, exclusion reasons, cell-level map |
        | **8 · Customer Segmentation** | Precomputed personas, sizes, profiles, cross-tabs |
        | **9 · Offer Recommendations** | Offer mix, tier-1 plans, add-ons, masked recommendation table |
        | **10 · What-If Simulation** | Take rate / uplift / PRB threshold scenarios (in-memory only) |

        ### Safety & privacy
        - Read-only connection (`default_transaction_read_only=on`) — SELECT only.
        - `msisdn` is never selected; subscriber identifiers are masked everywhere.
        - Credentials come from environment variables or `.streamlit/secrets.toml`.
        """
    )


if __name__ == "__main__":
    main()
