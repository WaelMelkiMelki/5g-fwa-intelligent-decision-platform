"""Page 6 — Data Quality.

Validates the approved ``cleaned_data`` objects against the verified
baselines documented in SCHEMA_MAPPING.md §1/§4/§5 and the official
``verify_schema_mapping.sql`` (sections 1-7). Every check is an aggregate
SELECT against allowlisted tables; NO subscriber identifiers are read and no
statement can write (read-only guard). Check | Result | Expected | Status |
Source table with PASS / WARNING / FAIL status.
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
from app.services import data_quality_service as dq
from app.state import session as S

st.set_page_config(page_title="Data Quality", page_icon="6️⃣", layout="wide")


def main() -> None:
    S.init_session()
    st.title("6 · Data Quality")
    st.caption(
        "Aggregate validation of the approved snapshot objects against verified "
        "baselines (SCHEMA_MAPPING §3, verify_schema_mapping.sql). Read-only."
    )

    F.render_global_filters()

    try:
        result = dq.run_all_checks()
    except Exception as exc:  # noqa: BLE001
        M.render_error_state(f"Could not run data-quality checks: {exc}")
        return

    summary = result["summary"]
    C.kpi_row(
        [
            {"label": "Overall", "value": summary["overall"],
             "help": "FAIL when any check fails; else PASS (WARN tolerated)"},
            {"label": "Checks run", "value": f"{summary['total']:,}",
             "help": "All checks are aggregate SELECTs (read-only)"},
            {"label": "PASS", "value": f"{summary['passed']:,}",
             "help": "Live value equals the documented baseline"},
            {"label": "Warnings", "value": f"{summary['warnings']:,}",
             "help": "Indicators not verifiable from the approved objects"},
        ],
        columns=4,
    )

    st.divider()
    checks = result["checks"]
    status_colours = {
        "PASS": "background-color: #e7f6e7; color: #1a7f37",
        "WARN": "background-color: #fff4cc; color: #8a6d00",
        "FAIL": "background-color: #fde2e2; color: #b3261e",
    }
    styled = checks.style.map(
        lambda v: status_colours.get(v, ""), subset=["status"]
    )
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "section": st.column_config.TextColumn("Section"),
            "check": st.column_config.TextColumn("Check"),
            "result": st.column_config.TextColumn("Result"),
            "expected": st.column_config.TextColumn("Expected"),
            "status": st.column_config.TextColumn("Status"),
            "source": st.column_config.TextColumn("Source"),
            "detail": st.column_config.TextColumn("Details"),
        },
    )

    if summary["fails"] == 0:
        st.success("All verifiable checks pass against the current snapshot.")
    else:
        M.render_warning(f"{summary['fails']} check(s) FAILED — inspect the table above.")

    st.info(
        "Historical data-quality trends are unavailable for the current "
        "snapshot (the pipeline stores a single snapshot month, 2026-01-01)."
    )


if __name__ == "__main__":
    main()
